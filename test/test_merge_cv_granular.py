import sys
from pathlib import Path
sys.path.insert(0, '/Users/display/PycharmProjects/jobs')
from flask_app import app
import json

def test_merge_granular():
    user_id = 6
    with app.test_client() as c:
        # simulate login as user 6
        with c.session_transaction() as sess:
            sess['login_id'] = user_id
        # Load available json file name
        base = Path(app.static_folder) / 'uploads' / 'users' / str(user_id) / 'cvs'
        json_files = [p for p in sorted(base.iterdir()) if p.suffix.lower() == '.json']
        assert len(json_files) >= 1, 'No json files to test'
        fname = json_files[0].name
        # read json and check a list section
        data = json.loads(json_files[0].read_text(encoding='utf-8'))
        work = data.get('work') or []
        if not work:
            # nothing to pick, skip
            return
        # pick first work item
        picks_field = f'pick__{fname}__work[]'
        resp = c.post(f'/merge_cvs_editor/{user_id}', data={picks_field: ['0']}, follow_redirects=True)
        assert resp.status_code == 200
        # check that a merged file was created in folder with prefix cv_merged_editor_
        merged_files = [p for p in base.iterdir() if p.name.startswith('cv_merged_editor_')]
        assert merged_files, 'merged file not created'
        # check content
        merged = json.loads(merged_files[-1].read_text(encoding='utf-8'))
        assert 'work' in merged
        # ensure first item equals original first
        assert merged['work'][0].get('position') == work[0].get('position')
        print('merge granular test ok')

if __name__ == '__main__':
    test_merge_granular()
    print('done')

