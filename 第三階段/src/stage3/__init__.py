"""SkinDetect 第三階段：多視角融合與部位標籤流程。"""

__all__ = ["MultiViewConvNeXt", "build_v10_model"]


def __getattr__(name):
    if name in __all__:
        from .models import MultiViewConvNeXt, build_v10_model

        return {"MultiViewConvNeXt": MultiViewConvNeXt, "build_v10_model": build_v10_model}[name]
    raise AttributeError(name)
