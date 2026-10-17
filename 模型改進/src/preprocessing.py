"""Aspect-preserving input sizing. Missing config deliberately means historical behavior."""
from PIL import Image


class Letterbox:
    def __init__(self, size, fill=(124,116,104), allow_upscale=True):
        if not isinstance(size, int) or size<1: raise ValueError('size must be positive integer')
        if len(fill)!=3 or any(not isinstance(v,int) or not 0<=v<=255 for v in fill):
            raise ValueError('fill must be three RGB integers in [0,255]')
        self.size,self.fill,self.allow_upscale=size,tuple(fill),allow_upscale

    def geometry(self, width, height):
        if min(width,height)<1: raise ValueError('Empty image')
        scale=min(self.size/width,self.size/height)
        if not self.allow_upscale: scale=min(scale,1.)
        w=max(1,min(self.size,round(width*scale)))
        h=max(1,min(self.size,round(height*scale)))
        left,top=(self.size-w)//2,(self.size-h)//2
        return {'resized_size':(w,h),'scale':scale,'content_box':(left,top,left+w,top+h),
                'padding_fraction':1-w*h/self.size**2}

    def __call__(self,image):
        image=image.convert('RGB')
        info=self.geometry(*image.size)
        resized=image.resize(info['resized_size'],Image.Resampling.BILINEAR)
        canvas=Image.new('RGB',(self.size,self.size),self.fill)
        canvas.paste(resized,info['content_box'][:2])
        return canvas


class ResizeToFit(Letterbox):
    """Resize real pixels first to keep full-resolution color augmentation inexpensive."""
    def __call__(self,image):
        return image.convert('RGB').resize(self.geometry(*image.size)['resized_size'],Image.Resampling.BILINEAR)


def mode(cfg):
    value=cfg.get('preprocessing',{}).get('mode','legacy')
    if value not in ['legacy','letterbox','stretch']: raise ValueError(f'Unknown preprocessing mode: {value}')
    return value


def spatial_transform(cfg):
    from torchvision import transforms
    if mode(cfg) in ['legacy','stretch']: return transforms.Resize((cfg['run']['size'],cfg['run']['size']))
    p=cfg['preprocessing']
    return Letterbox(cfg['run']['size'],p['fill'],p.get('allow_upscale',True))


def pilot_config(cfg, input_pilot):
    if input_pilot:
        cfg['preprocessing']['mode']=input_pilot
        cfg['input_pilot']={'train_per_source':1200,'select_per_source':200,'seed':17}
        cfg['training']['epochs']=2
        cfg['training']['patience']=2
    return cfg


class RealPixelInput:
    """NF2 sees only resized true pixels, before padding and normalization. No uint8 roundtrip."""
    def __init__(self,cfg,training=False,filter_chain=None):
        from torchvision import transforms
        self.cfg,self.filter_chain=cfg,filter_chain
        self.resize=ResizeToFit(cfg['run']['size'],cfg['preprocessing']['fill']) if mode(cfg)=='letterbox' else spatial_transform(cfg)
        self.augment=transforms.Compose([transforms.RandomHorizontalFlip(),transforms.RandomVerticalFlip(),
                         transforms.ColorJitter(.22,.22,.20,.03)]) if training else lambda x:x
        self.tensor=transforms.ToTensor()
        self.normalize=transforms.Normalize(cfg['normalization']['mean'],cfg['normalization']['std'])

    def pixels(self,image):
        return self.tensor(self.augment(self.resize(image)))

    def finish_pixels(self,x):
        import torch
        if mode(self.cfg)=='letterbox':
            size=self.cfg['run']['size']; h,w=x.shape[-2:]
            fill=torch.tensor(self.cfg['preprocessing']['fill'],dtype=x.dtype,device=x.device)/255
            canvas=fill[:,None,None].expand(3,size,size).clone()
            top,left=(size-h)//2,(size-w)//2
            canvas[:,top:top+h,left:left+w]=x
            x=canvas
        return x

    def finish(self,x): return self.normalize(self.finish_pixels(x))

    def __call__(self,image):
        import torch
        x=self.pixels(image)
        if self.filter_chain is not None:
            with torch.no_grad(): x=self.filter_chain(x.unsqueeze(0)).squeeze(0)
            if not torch.isfinite(x).all(): raise FloatingPointError('NF2 nonfinite pixels')
        return self.finish(x)
