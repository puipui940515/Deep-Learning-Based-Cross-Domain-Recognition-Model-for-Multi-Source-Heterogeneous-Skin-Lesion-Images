"""Deterministic CP005 crop estimates; estimates are not lesion ground truth."""
import sys
import numpy as np
from PIL import Image, ImageCms
from scipy import ndimage
from common import ROOT
import torch

sys.path.insert(0, str(ROOT / 'noisefilter_v2強化實驗/vendor'))
from noisefilter_v2.masks import ReferenceMask

_LAB = ImageCms.buildTransformFromOpenProfiles(ImageCms.createProfile('sRGB'), ImageCms.createProfile('LAB'), 'RGB', 'LAB')
_MASK = ReferenceMask()


def otsu(values):
    hist, edges = np.histogram(values, bins=256, range=(0, 256))
    p = hist.astype(float) / max(hist.sum(), 1)
    w = p.cumsum(); m = (p * np.arange(256)).cumsum()
    score = (m[-1] * w - m) ** 2 / np.maximum(w * (1 - w), 1e-12)
    return float(edges[int(score.argmax()) + 1])


def estimate(image, method='D2'):
    width, height = image.size
    small = image.copy(); small.thumbnail((512, 512))
    rgb = np.asarray(small.convert('RGB'), dtype=np.float32) / 255
    L = np.asarray(ImageCms.applyTransform(small.convert('RGB'), _LAB))[:, :, 0]
    valid = np.ones(L.shape, dtype=bool)
    if method == 'D2':
        with torch.no_grad():
            valid = _MASK.valid(torch.from_numpy(rgb).permute(2,0,1).unsqueeze(0))[0,0].numpy() > .5
        hsv = np.asarray(small.convert('HSV'), dtype=np.float32) / 255
        # Added heuristic for saturated blue/green markers; existing mask does not implement this.
        marker = (hsv[:,:,1] > .65) & (hsv[:,:,0] > .20) & (hsv[:,:,0] < .85)
        valid &= ~marker
    if valid.sum() < 16:
        return {'fallback': True, 'reason':'insufficient_valid_pixels', 'bbox':None, 'area_fraction':None}
    dark = (L < otsu(L[valid])) & valid
    kernel = max(1, round(min(L.shape) * .01))
    dark = ndimage.binary_opening(dark, structure=np.ones((kernel,kernel)))
    components, count = ndimage.label(dark)
    if count == 0:
        return {'fallback':True,'reason':'no_component','bbox':None,'area_fraction':None}
    sizes = np.bincount(components.ravel()); sizes[0] = 0
    yy, xx = np.where(components == sizes.argmax())
    x, y = xx.min()/L.shape[1]*width, yy.min()/L.shape[0]*height
    w, h = (xx.max()-xx.min()+1)/L.shape[1]*width, (yy.max()-yy.min()+1)/L.shape[0]*height
    area = w*h/(width*height)
    bad = area < .01 or area > .8 or max(w/h, h/w) > 5
    return {'fallback':bool(bad), 'reason':'geometry_limits' if bad else None,
            'bbox':[float(x),float(y),float(w),float(h)], 'area_fraction':float(area)}


def crop(image, method, k=1.5, estimate_record=None):
    if method == 'none':
        return image
    width,height = image.size
    record = estimate_record if estimate_record is not None else (estimate(image,method) if method != 'D0' else None)
    if method == 'D0' or record['fallback']:
        cx,cy,side = width/2,height/2,.7*min(width,height)
    else:
        x,y,w,h = record['bbox']; cx,cy,side = x+w/2,y+h/2,k*max(w,h)
    side = max(1,round(side)); left,top = round(cx-side/2),round(cy-side/2)
    # Edge padding preserves requested square extent without introducing black borders.
    arr = np.asarray(image.convert('RGB'))
    pads = (max(0,-top),max(0,top+side-height),max(0,-left),max(0,left+side-width))
    if any(pads):
        arr = np.pad(arr, ((pads[0],pads[1]),(pads[2],pads[3]),(0,0)), mode='edge')
    return Image.fromarray(arr[top+pads[0]:top+pads[0]+side, left+pads[2]:left+pads[2]+side])
