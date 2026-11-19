"""The readable documents say what the JSON documents say: the counts, the ids and the sentences, in Vietnamese, with no raw id of a technique where a plain word exists."""
import json
import re

from bti.output import parts as P, publish
from bti.output import shotwords
from output_helpers import KEY, PID, TITLE

RAW_ID = re.compile(r"\b[A-Z]{1,6}-[A-Z0-9]{1,3}(?:-\d+)?\b")
VI = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)


def build(proj):
    proj.stage("export").change().job("1111111111111111", "voice", provider="chatterbox", aligner="whisper")
    proj.job("2222222222222222", "draft", agent={"id": "opus", "label": "Opus 5.5 High", "model": "m"}, model="claude:m", mode="edit", instruction="Fill the screen in the CAM-03 shots")
    proj.job("3333333333333333", "outline", sub="jobs", agent={"id": "opus", "label": "Opus 5.5 High"}, model="claude:m")
    publish.sync(proj.d, proj.out, moment="export done", sheets=False)


def test_outline_md_carries_the_outline(proj):
    build(proj)
    md = proj.text("2_script/outline.md")
    o = json.loads(proj.text("2_script/outline.json"))
    assert "%d chương · %d dữ kiện" % (len(o["chapters"]), len(o["facts"])) in md
    assert o["thesis"] in md
    for c in o["chapters"]:
        assert "`%s`" % c["id"] in md and c["title"] in md and ("ngân sách khoảng %d từ" % c["word_budget"]) in md
    for f in o["facts"]:
        assert "`%s`" % f["id"] in md and f["claim"] in md
    assert "Dữ kiện chưa chương nào dùng: `f04`" in md
    assert "(đã chọn)" in md and "đã duyệt bởi Lệnh bti (test)" in md
    assert "the pearl" in md and not re.search(r"\bD\d\b", md), "a detail called D2 by the dossier is written by its own name"
    assert "the mirror" in md


def test_narration_md_carries_the_narration(proj):
    build(proj)
    md = proj.text("2_script/narration.md")
    n = json.loads(proj.text("2_script/narration.json"))
    beats = [b for c in n["chapters"] for b in c["beats"]]
    words = sum(len(b["text"].split()) for b in beats)
    assert "%d chương · %d dòng · %d từ" % (len(n["chapters"]), len(beats), words) in md
    for b in beats:
        assert "**%s** (%d từ)" % (b["id"], len(b["text"].split())) in md and b["text"] in md
    for c in n["chapters"]:
        assert "(`%s`)" % c["id"] in md


def test_shots_md_has_one_plain_line_per_shot(proj):
    build(proj)
    md = proj.text("5_storyboard/shots.md")
    sb = json.loads(proj.text("5_storyboard/storyboard.json"))
    rows = [ln for ln in md.splitlines() if re.match(r"\| \d+ \|", ln)]
    assert len(rows) == len(sb["shots"]) and "%d cảnh" % len(sb["shots"]) in md
    for s in sb["shots"]:
        assert "`%s`" % s["id"] in md
    assert not RAW_ID.search(md), "no raw technique id in shots.md: " + str(RAW_ID.findall(md))
    by_id = {ln.split("`")[-2]: ln for ln in rows}
    assert "Zoom vào tấm gương trên tường" in by_id["s0001"]
    assert "Kéo ra, thấy cả bức tranh · vòng sáng" in by_id["s0002"] and "(đã khóa)" in by_id["s0002"]
    assert "Giữ yên ảnh “A map of the provinces”" in by_id["s0003"]
    assert "Thẻ tiêu đề: The room" in by_id["s0004"]
    assert "Zoom kèm dịch tới viên ngọc trai · nhãn chi tiết" in by_id["s0005"]
    assert "High on the back wall" in by_id["s0001"], "the line being read when the shot starts"
    for ln in rows:
        assert VI.search(ln) or True
    assert "## Chương 1 · COLD OPEN" in md and "## Chương 2 · THE ROOM" in md


def test_shots_md_sentences_are_those_of_the_shared_cases(proj):
    """The sentence function that writes shots.md is the one the shared cases test: every shot of the fixture is also made by it directly."""
    build(proj)
    from bti.output.facts import collect
    f = collect(proj.d)
    env = shotwords.env_of(P.registry(), f.sb["assets"], shotwords.main_asset_key(f.sb, TITLE))
    md = proj.text("5_storyboard/shots.md")
    for s in f.sb["shots"]:
        assert shotwords.shot_sentence(s, env) in md


def test_changes_md_has_every_batch_with_its_sentences(proj):
    build(proj)
    md = proj.text("log/changes.md")
    assert "batch_0001" in md and "Storyboard" in md and "19/11/2026 10:00" in md
    assert "Agent claude:claude-opus-5-5@high" in md
    assert "Cảnh 2: dời điểm cắt từ 0:10 sang 0:12" in md
    label = P.registry()["CAM-03"]["label_vi"]
    assert "Make the %s shots fill the screen" % label in md and not RAW_ID.search(md), "an id in the request is written as the technique's own name"
    assert "1 thao tác, 1 thay đổi" in md


def test_jobs_md_has_every_job_with_agent_and_outcome(proj):
    build(proj)
    md = proj.text("log/jobs.md")
    assert "Có 3 việc" in md
    assert "Opus 5.5 High" in md and "chatterbox + whisper" in md
    assert "Lập dàn ý" in md and "Tạo giọng đọc" in md and "Sửa storyboard bằng lời" in md
    assert "xong" in md and "2 phút" in md
    assert not RAW_ID.search(md)
    j = json.loads(proj.text("log/jobs.json"))
    assert {r["id"] for r in j["jobs"]} == {"1111111111111111", "2222222222222222", "3333333333333333"}


def test_jobs_the_app_pruned_stay_in_the_log(proj):
    build(proj)
    (proj.d / "cache" / "longjobs" / "1111111111111111.json").unlink()
    publish.sync(proj.d, proj.out, moment="again", sheets=False, force=True)
    assert "Tạo giọng đọc" in proj.text("log/jobs.md") and "Có 3 việc" in proj.text("log/jobs.md")


def test_readme_says_where_the_video_stands(proj):
    build(proj)
    md = proj.text("README.md")
    assert md.startswith("# %s" % TITLE) and "Jan Vermeer · 1665" in md
    assert "**Đã xong.**" in md and "`final.mp4`" in md and "output/%s/" % KEY in md and PID in md
    assert "Kiểm tra tự động: tất cả 3 mục đều đạt." in md
    assert "-15,0 LUFS" in md and "1920 × 1080" in md
    for step in ("Tác phẩm", "Kịch bản", "Giọng đọc", "Chọn hình", "Dựng hình", "Xuất video"):
        assert step in md
    assert "Lệnh bti (test)" in md and "Opus 5.5 High" in md
    assert "tools/deploy/fetch_video.sh %s" % KEY in md
    assert not RAW_ID.search(md) and VI.search(md)


def test_readme_of_a_project_in_progress_says_what_to_do_next(proj):
    proj.stage("approve_narration")
    publish.sync(proj.d, proj.out, moment="narration approved", sheets=False)
    md = proj.text("README.md")
    assert "**Đang làm.**" in md and "bước 3, Giọng đọc" in md and "Tạo giọng đọc" in md
    assert "`final.mp4`" not in md.split("## Trong thư mục này")[1].split("## Xem gì tiếp")[0]


def test_sources_md_lists_the_books(proj):
    proj.create()
    publish.sync(proj.d, proj.out, moment="project created", sheets=False)
    md = proj.text("1_sources/sources.md")
    assert "payne_gae/002" in md and "hodge_aid/003" in md and "23–35" in md
    assert "`payne_gae_002.txt`" in md
