"""CPU 小測試；只使用自製色塊、替身分數與 HTTP，不載入任何真實模型。"""
import base64
import copy
import io
import json
import math
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from pathlib import Path

from ensemble_server import EnsembleServer, MAX_BODY, parse_request
from v2_inference.contract import ModelContract
from v2_inference.core import CLASS_CODES, SINGLE, ENSEMBLE, InferenceError, combine_probabilities, ranked_probabilities
from v2_inference.runtime import V2Predictor, open_rgb, gpu_idle_check

PROJECT = Path("D:/SkinDetect_base")
VECTOR = [.05, .1, .1, .1, .4, .1, .15]


def png():
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", (16, 12), (184, 208, 180)).save(out, format="PNG")
    return out.getvalue()


class FakeSession:
    """故意不 import torch；所有分數皆測試替身，不能當實際模型成果。"""
    def __init__(self, contract, device): self.mode = None
    def prepare(self, mode): self.mode = mode; return 1.0
    def score(self, image):
        members = (1,) if self.mode == SINGLE else (1, 2, 3)
        return {seed: VECTOR for seed in members}, dict(vram=None, forward_and_softmax_ms=0.0)
    def close(self): self.mode = None


class CoreTests(unittest.TestCase):
    def test_average_probabilities_not_logits_or_softmax(self):
        # 三成員刻意不同，驗證公式不是把一個成員複製三份。
        a, b, c = [.8, .2, 0, 0, 0, 0, 0], [.2, .8, 0, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0, 0]
        result = combine_probabilities(ENSEMBLE, {1:a, 2:b, 3:c})
        self.assertEqual(result, (1/3, 1/3, 1/3, 0, 0, 0, 0))
        self.assertEqual(ranked_probabilities(result)[0]["code"], "AKIEC")

    def test_single_is_unchanged(self):
        self.assertEqual(combine_probabilities(SINGLE, {1: VECTOR}), tuple(VECTOR))

    def test_missing_member_is_not_partial_ensemble(self):
        with self.assertRaises(InferenceError): combine_probabilities(ENSEMBLE, {1:VECTOR, 2:VECTOR})

    def test_reject_bad_scores(self):
        for vector in ([math.nan]*7, [math.inf]*7, [-.1,1.1,0,0,0,0,0], [0]*7, [1,0]):
            with self.subTest(vector=vector), self.assertRaises(InferenceError): combine_probabilities(SINGLE, {1:vector})

    def test_reject_unknown_model(self):
        for mode in ("other", [], None):
            with self.subTest(mode=mode), self.assertRaises(InferenceError): combine_probabilities(mode, {1:VECTOR})

    def test_metadata_without_model_payload(self):
        cfg = ModelContract(PROJECT).validate((1,2,3), weights=False)
        self.assertEqual(cfg["training"]["image_size"], 224)
        self.assertNotIn("torch", sys.modules)

    def test_wrong_class_order_stops(self):
        spec = copy.deepcopy(ModelContract(PROJECT).spec)
        spec["class_order"] = list(reversed(CLASS_CODES))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"bad.json"; path.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaises(InferenceError): ModelContract(PROJECT,path)

    def test_changed_contract_hash_stops(self):
        contract=ModelContract(PROJECT)
        contract.spec["config"]["sha256"] = "0"*64
        with self.assertRaises(InferenceError): contract.validate((1,), weights=False)


class RuntimeTests(unittest.TestCase):
    def test_default_gate_does_not_create_session(self):
        def forbidden(*args): raise AssertionError("Disabled model must never be loaded")
        predictor=V2Predictor(PROJECT,session_factory=forbidden)
        with self.assertRaises(InferenceError) as cm: predictor.predict(b"x",SINGLE)
        self.assertEqual(cm.exception.code,"EXECUTION_DISABLED")
        self.assertIsNone(predictor.session)
        self.assertNotIn("torch",sys.modules)

    def test_synthetic_image_and_fake_single(self):
        result=V2Predictor(PROJECT,enabled=True,session_factory=FakeSession).predict(png(),SINGLE,"synthetic.png")
        self.assertEqual(result["image"]["width"],16)
        self.assertFalse(result["calibrated"])
        self.assertEqual(len(result["members"]),1)
        self.assertEqual(result["disease"][0]["code"],"NV")

    def test_fake_ensemble_members_and_no_heatmap(self):
        result=V2Predictor(PROJECT,enabled=True,session_factory=FakeSession).predict(png(),ENSEMBLE)
        self.assertEqual([member["weight"] for member in result["members"]],[1/3]*3)
        self.assertFalse(result["heatmap"]["available"])

    def test_invalid_image_before_loading(self):
        def forbidden(*args): raise AssertionError("Invalid image must not load model")
        for data in (b"", b"broken png", b"<svg></svg>"):
            with self.subTest(data=data), self.assertRaises(InferenceError):
                V2Predictor(PROJECT,enabled=True,session_factory=forbidden).predict(data,SINGLE)

    def test_inflight_request_rejected(self):
        predictor=V2Predictor(PROJECT,enabled=True,session_factory=FakeSession)
        predictor.lock.acquire()
        try:
            with self.assertRaises(InferenceError) as cm: predictor.predict(png(),SINGLE)
            self.assertEqual(cm.exception.code,"INFERENCE_BUSY")
        finally: predictor.lock.release()

    def test_model_failure_never_returns_mock(self):
        class Broken(FakeSession):
            def score(self,image): raise RuntimeError("synthetic failure")
        with self.assertRaises(InferenceError) as cm:
            V2Predictor(PROJECT,enabled=True,session_factory=Broken).predict(png(),SINGLE)
        self.assertEqual(cm.exception.code,"MODEL_FAILURE")

    def test_request_validation(self):
        for body in ([],{},dict(model_id=[]),dict(model_id=SINGLE,image_data_url="[EMBEDDED_IMAGE_OMITTED]),
                     dict(model_id=SINGLE,image_data_url="[EMBEDDED_IMAGE_OMITTED])):
            with self.subTest(body=body),self.assertRaises(InferenceError): parse_request(body)

    def test_gpu_guard_other_process(self):
        class Reply: stdout="999999, C:\\worker\\python.exe\n"
        with patch("v2_inference.runtime.subprocess.run",return_value=Reply()):
            with self.assertRaises(InferenceError) as cm: gpu_idle_check()
        self.assertEqual(cm.exception.code,"GPU_BUSY")

    def test_gpu_guard_unknown_fails_closed(self):
        with patch("v2_inference.runtime.subprocess.run",side_effect=OSError("missing")):
            with self.assertRaises(InferenceError) as cm: gpu_idle_check()
        self.assertEqual(cm.exception.code,"GPU_STATUS_UNKNOWN")

    def test_gpu_guard_no_model_import(self):
        class Reply: stdout="12004, C:\\Windows\\explorer.exe\n31352, C:\\app\\ChatGPT.exe\n"
        with patch("v2_inference.runtime.subprocess.run",return_value=Reply()): gpu_idle_check()
        self.assertNotIn("torch",sys.modules)


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor=V2Predictor(PROJECT)
        cls.server=EnsembleServer(("127.0.0.1",0),PROJECT/"ui_prototype/static/showcase_v1",cls.predictor)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f"http://127.0.0.1:{cls.server.server_port}"
    @classmethod
    def tearDownClass(cls): cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def request(self,path,body=None,origin=None):
        headers={"Content-Type":"application/json"}
        if origin: headers["Origin"]=origin
        req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=5) as response:return response.status,response.read()
        except urllib.error.HTTPError as error:return error.code,error.read()
    def test_health_never_loads_model(self):
        status,raw=self.request("/api/v2/health")
        self.assertEqual(status,200);self.assertFalse(json.loads(raw)["execution_enabled"])
        self.assertIsNone(self.predictor.session);self.assertNotIn("torch",sys.modules)
    def test_real_prediction_is_explicitly_disabled(self):
        status,raw=self.request("/api/v2/predict",dict(model_id=SINGLE,image_data_url="[EMBEDDED_IMAGE_OMITTED])).decode()))
        self.assertEqual(status,503);self.assertEqual(json.loads(raw)["code"],"EXECUTION_DISABLED")
    def test_training_route_absent(self):
        status,_=self.request("/api/training/start",{})
        self.assertEqual(status,404)
    def test_cross_origin_rejected(self):
        status,_=self.request("/api/v2/predict",{},origin="https://other.example")
        self.assertEqual(status,403)
    def test_static_and_traversal(self):
        self.assertEqual(self.request("/index.html")[0],200)
        self.assertEqual(self.request("/../../AGENTS.md")[0],404)
    def test_invalid_json_shape(self):
        status,raw=self.request("/api/v2/predict",[])
        self.assertEqual(status,400);self.assertEqual(json.loads(raw)["code"],"INVALID_REQUEST")


if __name__=="__main__": unittest.main(verbosity=2)
