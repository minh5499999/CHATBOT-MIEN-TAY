"""Isolated end-to-end checks for the conversational response flow."""
from pathlib import Path
import sys

# Reuse the demo harness that copies review evidence, never user SQLite.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'audit'))
mode=sys.argv[1]
if mode=='flow':sys.argv[1]='demo'
from run_m5final_checks import runner
for field in ('BUILD','BOOT','INSTALL','UI','RESTART'):
    setattr(runner,field,getattr(runner,field).replace(
        'release_candidate_20261118_m5_v2','release_candidate_20261118_m5_v3'))

if mode=='flow':
    i=runner.UI.index("from backend.chatbot.knowledge_policy import enforce_result")
    j=runner.UI.index("send('Cách làm gỏi gà bắp cải",i)
    runner.UI=runner.UI[:j]+r"""
for question in ('tôi đang bị sốt thì nên ăn món gì',
                 'Em đang sốt, bữa tối nấu món chi mềm dễ ăn?',
                 'Mình bị ho thì có món nào dễ ăn không?'):
    r=send(question,'COMFORT_MEAL_OPTIONS',('món mềm',))
    assert r['goi_y'] and all('cháo' in title.casefold() for title in r['goi_y'])
    chosen=r['nguon'][0]['id_goc']
    r=send('Cho tôi món số 1','SOURCE_UNVERIFIED',('Nguyên liệu','Cách chế biến'))
    assert r['chu_de']['id_goc']==chosen
    r=send('Hướng dẫn nấu món đó đi','SOURCE_UNVERIFIED',('Nguyên liệu','Cách chế biến'))
    assert r['chu_de']['id_goc']==chosen
send('Tui còn sốt, chỉ tui cách làm đậu bắp xào tỏi.','SOURCE_UNVERIFIED',('Đậu bắp 200g',))
r=send('Cho 6 người rồi giảm dầu một nửa','EDIT_APPLIED',('Khẩu phần','Dầu ăn: 2 muỗng canh'))
assert r['trang_thai']['recipe_edit_v1']['events'][-2]['command']['kind']=='scale'
assert r['trang_thai']['recipe_edit_v1']['events'][-1]['command']['kind']=='fraction'
r=send('Bỏ hạt nêm và giảm dầu ăn còn 100 muỗng canh','EDIT_UNSUPPORTED',('giữ nguyên',))
assert len(r['trang_thai']['recipe_edit_v1']['events'])==2
r=send('Viết lại cách nấu','EDIT_REWRITTEN',('Dầu ăn: 2 muỗng canh','Chưa có số liệu'))
assert 'hạt nêm' in r['cau_tra_loi']
send('Dùng món này để điều trị sốt được không?','HEALTH_CURE_UNSUPPORTED',())
app.button(key='dang_xuat').click().run()
app.text_input[0].set_value('p276_activation_test');app.text_input[1].set_value('LocalTest!2026')
next(b for b in app.button if b.label=='Đăng nhập').click().run()
send('Chỉ tui luộc bắp cải và cho xem calo','SOURCE_UNVERIFIED',(
  'Nguyên liệu','Dinh dưỡng mỗi khẩu phần','22.25 kcal','Protein: 1.139 g',
  'Chất béo: 0.089 g','Carbohydrate: 5.162 g','Natri: 16.02 mg','FDC 169975'))
send('Hướng dẫn làm bắp cải luộc.','SOURCE_UNVERIFIED',('Nguyên liệu','22.25 kcal'))
""" + runner.UI[j:]
if __name__=='__main__':runner.main()

