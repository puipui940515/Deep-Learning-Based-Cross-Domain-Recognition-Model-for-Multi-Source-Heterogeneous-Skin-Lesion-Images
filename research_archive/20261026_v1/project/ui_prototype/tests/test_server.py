from __future__ import annotations

import base64
import io
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Handler, Predictor, SkinDetectServer, prediction_payload, render_manual
from training_runtime import validate_parameters


def image_bytes(exif=False):
    buffer = io.BytesIO()
    im = Image.new('RGB', (30, 20), 'white')
    if exif:
        tags = Image.Exif()
        tags[274] = 6
        im.save(buffer, format='JPEG', exif=tags)
    else:
        im.save(buffer, format='PNG')
    return buffer.getvalue()


def demo_payload():
    return {'image_data_url': '[EMBEDDED_IMAGE_OMITTED] + base64.b64encode(image_bytes()).decode(),
            'model_id':'demo', 'image_name':'中文圖片.png', 'experiment_tag':'中文測試',
            'include_heatmap':False, 'include_site':False}


@pytest.fixture
def service():
    class TrainingStub:
        def status(self): return {'current':None, 'history':[], 'capabilities':{}}
    predictor = Predictor(Path('absent.pt'), Path('absent_site.pt'), 'cpu')
    server = SkinDetectServer(('127.0.0.1', 0), Handler, predictor, TrainingStub(), 'prototype')
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()
    server.server_close()
    thread.join()


def test_http_demo_and_history_have_matching_metadata(service):
    request = urllib.request.Request(service+'/api/predict', data=json.dumps(demo_payload()).encode(),
                                     headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request) as response: result=json.load(response)
    with urllib.request.urlopen(service+'/api/history') as response: history=json.load(response)
    assert result['image_name']=='中文圖片.png'
    assert len(result['disease'])==7
    assert sum(x['probability'] for x in result['disease'])==pytest.approx(1)
    assert history[0]['model_id']=='demo'
    assert history[0]['top_disease']['label']==result['disease'][0]['label']


def test_http_invalid_json_shape_is_explicit_error(service):
    request=urllib.request.Request(service+'/api/predict', data=b'[]', headers={'Content-Type':'application/json'})
    with pytest.raises(urllib.error.HTTPError) as caught: urllib.request.urlopen(request)
    assert caught.value.code==400
    assert 'JSON' in json.load(caught.value)['error']


def test_api_default_model_and_handbook(service):
    with urllib.request.urlopen(service+'/api/models') as response: models=json.load(response)
    assert 'default_model' in models
    assert all(x['class_count']==7 for x in models['models'] if x['kind']=='real')
    with urllib.request.urlopen(service+'/manual') as response: manual=response.read().decode()
    assert 'SkinDetect' in manual and '使用手冊' in manual
    assert '<img' in manual or '<pre><code>' in manual
    with urllib.request.urlopen(service+'/manual.md') as response: original=response.read().decode()
    assert 'CP-005' in original


def test_image_handbook_serving_does_not_escape_folder(service):
    with urllib.request.urlopen(service+'/manual-images/01_SkinDetect%20UI%20%E4%BD%BF%E7%94%A8%E6%89%8B%E5%86%8A.png') as response:
        assert response.headers['Content-Type']=='image/png'
        assert response.read(8)==b'\x89PNG\r\n\x1a\n'
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(service+'/manual-images/%2e%2e/server.py')
    assert caught.value.code==404


@pytest.mark.parametrize('change', [{'include_site':'false'}, {'image_data_url':'data:text/plain;base64,YQ=='},
                                  {'image_data_url':'[EMBEDDED_IMAGE_OMITTED] {'experiment_tag':'x'*201}])
def test_bad_payload_is_rejected(change):
    payload=demo_payload(); payload.update(change)
    with pytest.raises(ValueError): prediction_payload(payload,'demo')


def test_exif_orientation_used_by_prediction():
    predictor=Predictor(Path('absent.pt'),Path('absent.pt'),'cpu')
    result=predictor.predict(image_bytes(True),'demo',False,False,'','orientation')
    assert (result['image']['width'],result['image']['height'])==(20,30)


def test_corrupt_image_has_readable_error():
    predictor=Predictor(Path('absent.pt'),Path('absent.pt'),'cpu')
    with pytest.raises(ValueError,match='損毀'):
        predictor.predict(b'broken image','demo',False,False,'','')


def test_class_mismatch_is_not_silently_truncated():
    with pytest.raises(ValueError,match='不一致'): Predictor._ranked([('NV','痣')],[.5,.5])


@pytest.mark.parametrize('payload',[{'epochs':1.5},{'epochs':float('inf')},[],{'seed':True}])
def test_bad_training_parameters_never_launch(payload):
    with pytest.raises(ValueError): validate_parameters(payload)


def test_manual_escapes_html():
    assert '<script>' not in render_manual('# <script>\n- <img src=x>')
