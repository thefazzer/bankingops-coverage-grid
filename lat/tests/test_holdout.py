"""C7 / T6: holdout commit / reveal / verify; near-dup detection via MinHash sketches."""
import copy

from lat import holdout as H


ITEMS = [{"item_id": "HITEM-0001", "task_text": "identify the root cause of the returned payment and propose the fix",
          "answer": "purpose code missing", "source_doc_ids": []},
         {"item_id": "HITEM-0002", "task_text": "explain why the affirmation was rejected and state the next action",
          "answer": "notional mismatch", "source_doc_ids": []}]


def test_commit_reveal_verify_and_swap():
    public, secret = H.make_commit("HOLD-1", ITEMS)
    assert public["n_items"] == 2 and "answer" not in str(public) and "purpose code" not in str(public)
    reveal = {"holdout_id": "HOLD-1", "nonce_h": secret["nonce_h"], "items": secret["items"]}
    assert H.verify_reveal(public, reveal)[0]
    # T6: items/answers swapped after scores were seen -> commitment does not open
    swapped = copy.deepcopy(reveal)
    swapped["items"][0]["answer"] = "beneficiary bank error"
    assert not H.verify_reveal(public, swapped)[0]
    swapped2 = copy.deepcopy(reveal)
    swapped2["items"].append({"item_id": "HITEM-0003", "task_text": "new", "answer": "x", "source_doc_ids": []})
    assert not H.verify_reveal(public, swapped2)[0]
    # wrong nonce
    wrong = dict(reveal, nonce_h="00" * 32)
    assert not H.verify_reveal(public, wrong)[0]
    # item order does not matter (canonical payload)
    reordered = dict(reveal, items=list(reversed(reveal["items"])))
    assert H.verify_reveal(public, reordered)[0]


def test_near_dup_sketches():
    public, _ = H.make_commit("HOLD-1", ITEMS)
    near = "identify the root cause of the returned payment and propose the fix now"
    far = "the break is a timing difference and will roll off at the next batch"
    hits = H.near_dups_against_sketches([("ep-1", near), ("ep-2", far)], public)
    assert [h["label"] for h in hits] == ["ep-1"] and hits[0]["item_id"] == "HITEM-0001"
    hits2 = H.near_dups_against_items([("ep-1", near), ("ep-2", far)], ITEMS)
    assert [h["label"] for h in hits2] == ["ep-1"]
