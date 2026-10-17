"""Train-only examples, not model predictions."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import EXP,ROOT,load,read_rows,write
from preprocessing import Letterbox
from PIL import Image,ImageOps
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    cfg=load(EXP/'config.json'); rows=read_rows(ROOT/cfg['manifest'])
    selected={}
    for r in rows:
        if r['split']=='train' and r['source'] not in selected: selected[r['source']]=r
    plt.rcParams['font.sans-serif']=['Microsoft JhengHei','SimHei','DejaVu Sans']
    fig,axes=plt.subplots(len(selected),3,figsize=(11,3*len(selected)),squeeze=False)
    transform=Letterbox(cfg['runs']['R0']['size'],cfg['preprocessing']['fill'])
    records=[]
    for i,(source,row) in enumerate(sorted(selected.items())):
        with Image.open(ROOT/row['image_path']) as original:
            im=ImageOps.exif_transpose(original).convert('RGB')
        info=transform.geometry(*im.size)
        images=[im,im.resize((224,224),Image.Resampling.BILINEAR),transform(im)]
        titles=[f'原圖 {im.width}×{im.height}', '直接縮放：可能變形',f'等比例補邊：補邊占 {info["padding_fraction"]:.1%}']
        for ax,image,title in zip(axes[i],images,titles):
            ax.imshow(image); ax.set_title(title); ax.set_xticks([]); ax.set_yticks([])
        axes[i,0].set_ylabel(source)
        records.append({'source':source,'record_id':row['record_id'],'original_size':im.size,**info})
    fig.suptitle('四來源輸入處理比較（僅示例，非效能結果）')
    fig.tight_layout(rect=(0,0,1,.97))
    destination=EXP/'reports/等比例補邊比較.png'
    fig.savefig(destination,dpi=140); plt.close(fig)
    write(destination.with_suffix('.json'),{'records':records,'preprocessing':cfg['preprocessing']})
    print(destination)


if __name__=='__main__': main()
