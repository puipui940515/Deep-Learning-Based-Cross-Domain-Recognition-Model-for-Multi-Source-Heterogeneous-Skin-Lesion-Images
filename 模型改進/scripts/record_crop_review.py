"""Record the 2026-10-06 assistant visual audit and render actual crop comparisons."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT,EXP,load,read_rows,write,sha
from geometry import estimate,crop
from PIL import Image,ImageOps
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    rows=read_rows(ROOT/'模型基底篩選_熱力圖10張測試/data/selected_samples.csv')
    notes={
        'S01':'框大致涵蓋中央深色區域；不代表定位真值',
        'S02':'框大致涵蓋中央深色區域；邊緣仍需人工確認',
        'S03':'只涵蓋下半部，遗漏上方可見紋理區域',
        'S04':'選到右側孔徑邊緣，偏離中央可見病灶',
        'S05':'框偏大，包含許多背景；定位優勢不明',
        'S06':'框到左側背景，遗漏中央偏右可見紅色區域',
        'S07':'外框幾乎覆蓋全圖，需回退中心裁切',
        'S08':'框偏大且偏右，未顯示可靠的局部定位',
        'S09':'框到上方陰影，遗漏中央可見病灶',
        'S10':'只選最大深色區域，沒有涵蓋上方另一區域；多病灶限制',
    }
    evidence=[]
    plt.rcParams['font.sans-serif']=['Microsoft JhengHei','SimHei','DejaVu Sans']
    fig,axes=plt.subplots(5,4,figsize=(16,20))
    for index,r in enumerate(rows):
        with Image.open(ROOT/r['image_path']) as im:
            im=ImageOps.exif_transpose(im).convert('RGB'); est=estimate(im)
            cut=crop(im,'D2',1.5,est)
        left=axes[index//2,(index%2)*2];right=axes[index//2,(index%2)*2+1]
        with Image.open(EXP/f'reports/R0_bbox_overlay/{index+1:02d}.png') as overlay:
            left.imshow(overlay.copy())
        right.imshow(cut)
        left.set_title(f'{r["sample_id"]} {r["source"]}\n原圖與估計框',fontsize=9)
        right.set_title('實際中心回退裁切' if est['fallback'] else '實際裁切（k=1.5）',fontsize=9)
        left.axis('off');right.axis('off')
        evidence.append({'sample_id':r['sample_id'],'record_id':r['record_id'],
                         'image_path':r['image_path'],'estimate':est,'observation':notes[r['sample_id']]})
    fig.tight_layout(); fig.savefig(EXP/'reports/R0_固定十張裁切檢查.png',dpi=110);plt.close(fig)
    write(EXP/'reports/R0_visual_review.json',{'reviewer':'assistant_visual_inspection',
          'human_approved':False,'accepted':False,'samples':evidence,
          'conclusion':'S04/S06/S09 show clear background/shadow selection; keep D2 locked.',
          'note':'Qualitative visual audit only; no ground-truth masks or localization score.'})
    gate_path=EXP/'reports/R0_bbox_stats.json'
    gate=load(gate_path)
    gate.update({'visual_review_approved':False,'passed':False,
                 'visual_review_status':'not_passed_assistant_review',
                 'visual_review_evidence':'模型改進/reports/R0_visual_review.json'})
    write(gate_path,gate)
    print('D2 remains locked; visual evidence saved.')


if __name__=='__main__': main()
