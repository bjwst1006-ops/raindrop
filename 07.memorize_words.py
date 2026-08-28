import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

import streamlit as st

DATA_FILE = os.path.join(os.path.dirname(__file__), "vocab.json")
BOX_INTERVALS = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}


def get_today_iso(today=None):
    if today is None:
        return datetime.now().strftime("%Y-%m-%d")
    return datetime.strptime(today, "%Y-%m-%d").strftime("%Y-%m-%d")


def add_days(date_text, days):
    current = datetime.strptime(date_text, "%Y-%m-%d").date()
    return (current + timedelta(days=days)).isoformat()


def load_vocab(path=DATA_FILE):
    if not os.path.exists(path):
        save_vocab([], path)
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("Vocabulary data must be a list.")
        return data
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Failed to load vocabulary: {exc}")
        return []


def save_vocab(words, path=DATA_FILE):
    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(words, file, ensure_ascii=False, indent=2)
            file.write("\n")
    except OSError as exc:
        print(f"Failed to save vocabulary: {exc}")
        raise


def get_next_id(words):
    if not words:
        return 1
    return max(int(item.get("id", 0)) for item in words) + 1


def normalize_word(word):
    cleaned = re.sub(r"\s+", " ", word.strip())
    if not cleaned:
        raise ValueError("Word cannot be empty.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z'\- ]*[A-Za-z]", cleaned) and not re.fullmatch(r"[A-Za-z]", cleaned):
        raise ValueError("Word must contain English letters only.")
    return cleaned


def normalize_meaning(meaning):
    cleaned = re.sub(r"\s+", " ", meaning.strip())
    if not cleaned:
        raise ValueError("Meaning cannot be empty.")
    return cleaned


def normalize_example(example):
    if example is None:
        return ""
    cleaned = re.sub(r"\s+", " ", example.strip())
    return cleaned


def normalize_part_of_speech(value):
    if value is None:
        return "기타"
    cleaned = re.sub(r"\s+", " ", str(value).strip())
    if not cleaned:
        return "기타"
    mapping = {
        "noun": "명사",
        "명사": "명사",
        "verb": "동사",
        "동사": "동사",
        "adjective": "형용사",
        "형용사": "형용사",
        "adverb": "부사",
        "부사": "부사",
        "pronoun": "대명사",
        "대명사": "대명사",
        "preposition": "전치사",
        "전치사": "전치사",
        "conjunction": "접속사",
        "접속사": "접속사",
        "article": "관사",
        "관사": "관사",
        "interjection": "감탄사",
        "감탄사": "감탄사",
        "phrase": "구",
        "expression": "표현",
        "idiom": "숙어",
    }
    return mapping.get(cleaned.lower(), cleaned)


def add_word(words, word, meaning, example="", part_of_speech="명사"):
    normalized_word = normalize_word(word)
    normalized_meaning = normalize_meaning(meaning)
    normalized_example = normalize_example(example)
    normalized_part = normalize_part_of_speech(part_of_speech)

    item = {
        "id": get_next_id(words),
        "word": normalized_word,
        "meaning": normalized_meaning,
        "example": normalized_example,
        "part_of_speech": normalized_part,
        "box": 1,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_review": None,
        "next_review": get_today_iso(),
        "correct_streak": 0,
        "wrong_streak": 0,
    }
    words.append(item)
    return item


def get_due_words(words, today=None):
    current_day = get_today_iso(today)
    due = []
    for item in words:
        next_review = item.get("next_review")
        if not next_review:
            due.append(item)
            continue
        if next_review <= current_day:
            due.append(item)

    def sort_key(item):
        next_review = item.get("next_review") or current_day
        is_due_today = 0 if next_review == current_day else 1
        return (is_due_today, next_review, item.get("id", 0))

    return sorted(due, key=sort_key)


def process_quiz_result(item, is_correct, today=None):
    current_day = get_today_iso(today)
    item = dict(item)
    if is_correct:
        item["box"] = min(5, int(item.get("box", 1)) + 1)
        item["correct_streak"] = int(item.get("correct_streak", 0)) + 1
        item["wrong_streak"] = 0
    else:
        item["box"] = 1
        item["correct_streak"] = 0
        item["wrong_streak"] = int(item.get("wrong_streak", 0)) + 1

    item["last_review"] = current_day
    item["next_review"] = add_days(current_day, BOX_INTERVALS.get(item.get("box", 1), 1))
    return item


def get_review_summary(words, today=None):
    current_day = get_today_iso(today)
    due = get_due_words(words, current_day)
    total = len(words)
    boxes = {box: 0 for box in range(1, 6)}
    for item in words:
        box = int(item.get("box", 1))
        if 1 <= box <= 5:
            boxes[box] += 1
    return {
        "total": total,
        "due": len(due),
        "boxes": boxes,
    }


def list_words(words, review_due_only=False, today=None):
    current_day = get_today_iso(today)
    items = get_due_words(words, current_day) if review_due_only else list(words)
    items = sorted(items, key=lambda item: (item.get("next_review") or "9999-12-31", item.get("id", 0)))

    print("\n📚 📝 단어 목록")
    if not items:
        if review_due_only:
            print("📭 오늘 복습할 단어가 없습니다. 잠시 쉬어가세요! ☕")
        else:
            print("📭 저장된 단어가 없습니다. 새 단어를 추가해 보세요! ✍️")
        return []

    print(f"{'ID':>3} | {'WORD':<18} | {'POS':<6} | {'BOX':>3} | {'NEXT':<10} | {'MEANING':<18}")
    print("-" * 82)
    for item in items:
        word = str(item.get("word", "-"))
        meaning = str(item.get("meaning", "-"))
        pos = str(item.get("part_of_speech", "기타"))
        box = item.get("box", 1)
        next_review = item.get("next_review") or "-"
        print(f"{item.get('id', 0):>3} | {word:<18} | {pos:<6} | {box:>3} | {next_review:<10} | {meaning:<18}")
    return items


def quiz(words, today=None):
    current_day = get_today_iso(today)
    while True:
        due_items = get_due_words(words, current_day)
        if not due_items:
            print("✅ 오늘 복습이 모두 완료되었습니다! 멋져요! 🌟")
            return True

        target = due_items[0]
        print(f"\n🧠 복습 우선 퀴즈! 오늘 복습할 단어를 자동으로 이어서 출제합니다.")
        print(f"📌 [{target['id']}] 단어: {target['word']} | 품사: {target.get('part_of_speech', '기타')} | 현재 박스: {target['box']}")
        if target.get("example"):
            print(f"💬 예문: {target['example']}")

        try:
            user_answer = input("✍️ 뜻을 입력하세요: ").strip()
        except EOFError:
            raise SystemExit(0)

        normalized_answer = normalize_meaning(user_answer)
        normalized_target = normalize_meaning(target.get("meaning", ""))
        is_correct = normalized_answer.lower() == normalized_target.lower()

        if is_correct:
            print(f"✅ 정답입니다! '{target['meaning']}'")
        else:
            print(f"❌ 오답입니다. 정답은 '{target['meaning']}' 입니다.")

        updated_target = process_quiz_result(target, is_correct, current_day)
        for index, item in enumerate(words):
            if item.get("id") == target.get("id"):
                words[index] = updated_target
                break

        print("➡️ 다음 문제를 이어서 출제합니다...")


def delete_word(words, word_id):
    try:
        target_id = int(word_id)
    except (TypeError, ValueError):
        raise ValueError("ID must be a number.")

    for index, item in enumerate(words):
        if int(item.get("id", -1)) == target_id:
            removed = words.pop(index)
            return removed
    raise ValueError(f"ID {target_id} not found.")


def prompt_text(prompt):
    while True:
        try:
            value = input(prompt).strip()
        except EOFError:
            raise SystemExit(0)
        if value:
            return value
        print("입력은 비워둘 수 없습니다.")


def prompt_example(prompt):
    try:
        value = input(prompt).strip()
    except EOFError:
        raise SystemExit(0)
    if not value:
        return ""
    return value


def prompt_part_of_speech(prompt):
    options = {
        "1": "명사",
        "2": "동사",
        "3": "형용사",
        "4": "부사",
        "5": "기타",
    }
    while True:
        try:
            value = input(prompt).strip().lower()
        except EOFError:
            raise SystemExit(0)
        if not value:
            return "명사"
        if value in options:
            return options[value]
        if value in {"noun", "명사"}:
            return "명사"
        if value in {"verb", "동사"}:
            return "동사"
        if value in {"adjective", "형용사"}:
            return "형용사"
        if value in {"adverb", "부사"}:
            return "부사"
        if value in {"other", "기타"}:
            return "기타"
        print("⚠️ 1~5 중에서 선택하세요: 1=명사, 2=동사, 3=형용사, 4=부사, 5=기타")


def interactive_menu():
    while True:
        words = load_vocab()
        summary = get_review_summary(words)
        print("\n========================================")
        print("📘 영어 단어 암기 앱 📘")
        print(f"📊 총 단어: {summary['total']}개 | 오늘 복습: {summary['due']}개 | Box 1~5: {summary['boxes']}")
        print("========================================")
        print("1. 📚 단어 추가")
        print("2. 📋 전체 목록")
        print("3. 🗓️ 오늘 복습 보기")
        print("4. 🧠 퀴즈")
        print("5. 🗑️ 삭제")
        print("6. 🚪 종료")

        try:
            choice = input("👉 선택하세요: ").strip().lower()
        except EOFError:
            raise SystemExit(0)

        if choice in {"1", "add", "a"}:
            print("\n📝 새 단어를 추가합니다.")
            word = prompt_text("🔤 영어 단어: ")
            meaning = prompt_text("🇰🇷 의미(한국어): ")
            example = prompt_example("💬 예문(선택, 엔터 입력 시 생략): ")
            part_of_speech = prompt_part_of_speech("🧩 품사 선택(1=명사, 2=동사, 3=형용사, 4=부사, 5=기타): ")
            words = load_vocab()
            item = add_word(words, word, meaning, example, part_of_speech)
            save_vocab(words)
            print(f"✅ 저장 완료! #{item['id']} {item['word']} - {item['meaning']} [{item['part_of_speech']}]")
        elif choice in {"2", "list", "l"}:
            list_words(load_vocab())
        elif choice in {"3", "today", "due", "t"}:
            list_words(load_vocab(), review_due_only=True)
        elif choice in {"4", "quiz", "review", "q"}:
            words = load_vocab()
            quiz(words)
            save_vocab(words)
        elif choice in {"5", "delete", "d"}:
            words = load_vocab()
            if not words:
                print("📭 삭제할 단어가 없습니다.")
                continue
            list_words(words)
            try:
                target_id = input("🗑️ 삭제할 ID를 입력하세요: ").strip()
            except EOFError:
                raise SystemExit(0)
            try:
                delete_word(words, target_id)
                save_vocab(words)
                print(f"✅ ID {target_id} 항목이 삭제되었습니다.")
            except ValueError as exc:
                print(f"⚠️ 삭제 실패: {exc}")
        elif choice in {"6", "exit", "quit", "e", "x"}:
            print("👋 프로그램을 종료합니다. 다음에 다시 만나요! 😊")
            break
        else:
            print("⚠️ 잘못된 선택입니다. 1~6 또는 명령어를 입력하세요.")


def build_parser():
    parser = argparse.ArgumentParser(description="Leitner 영어 단어 암기 앱")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="새 단어 추가")
    add_parser.add_argument("word")
    add_parser.add_argument("meaning")
    add_parser.add_argument("--example", dest="example", default="")

    list_parser = subparsers.add_parser("list", help="단어 목록 보기")
    list_parser.add_argument("--due", action="store_true", help="오늘 복습할 항목만 보기")

    quiz_parser = subparsers.add_parser("quiz", help="오늘 복습 퀴즈")
    quiz_parser.add_argument("--word-id", type=int, default=None, help="특정 단어 ID로 퀴즈를 시작합니다.")

    delete_parser = subparsers.add_parser("delete", help="단어 삭제")
    delete_parser.add_argument("word_id", type=int)

    return parser


def render_word_table(words, title="단어 목록"):
    st.subheader(title)
    if not words:
        st.info("표시할 단어가 없습니다.")
        return

    table_data = [
        {
            "ID": item.get("id"),
            "단어": item.get("word", ""),
            "뜻": item.get("meaning", ""),
            "품사": item.get("part_of_speech", "기타"),
            "Box": item.get("box", 1),
            "다음 복습일": item.get("next_review") or "-",
            "예문": item.get("example") or "-",
        }
        for item in words
    ]
    st.dataframe(table_data, use_container_width=True, hide_index=True)


def render_add_tab(words):
    with st.form("add_word_form", clear_on_submit=True):
        word = st.text_input("영어 단어", placeholder="예: resilient")
        meaning = st.text_input("한국어 뜻", placeholder="예: 회복력이 있는")
        example = st.text_input("예문", placeholder="선택 사항")
        part_of_speech = st.selectbox(
            "품사",
            ["명사", "동사", "형용사", "부사", "기타"],
        )
        submitted = st.form_submit_button("단어 저장", type="primary")

    if submitted:
        try:
            item = add_word(words, word, meaning, example, part_of_speech)
            save_vocab(words)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(f"#{item['id']} {item['word']} 단어를 저장했습니다.")


def render_review_tab(words):
    feedback = st.session_state.pop("quiz_feedback", None)
    if feedback:
        feedback_type, feedback_message = feedback
        getattr(st, feedback_type)(feedback_message)

    due_words = get_due_words(words)
    render_word_table(due_words, "오늘 복습할 단어")

    if not due_words:
        return

    target = due_words[0]
    st.divider()
    st.markdown(f"### 퀴즈: **{target['word']}**")
    st.caption(
        f"품사: {target.get('part_of_speech', '기타')} · "
        f"현재 Box: {target.get('box', 1)}"
    )
    if target.get("example"):
        st.caption(f"예문: {target['example']}")

    with st.form("quiz_form"):
        answer = st.text_input("뜻을 입력하세요")
        submitted = st.form_submit_button("정답 확인", type="primary")

    if submitted:
        try:
            normalized_answer = normalize_meaning(answer)
        except ValueError:
            st.error("뜻을 입력해 주세요.")
            return

        is_correct = normalized_answer.lower() == normalize_meaning(target["meaning"]).lower()
        updated_target = process_quiz_result(target, is_correct)
        for index, item in enumerate(words):
            if item.get("id") == target.get("id"):
                words[index] = updated_target
                break
        save_vocab(words)
        if is_correct:
            st.session_state.quiz_feedback = (
                "success",
                f"정답입니다! 다음 복습일: {updated_target['next_review']}",
            )
        else:
            st.session_state.quiz_feedback = (
                "error",
                f"오답입니다. 정답은 '{target['meaning']}'입니다.",
            )
        st.rerun()


def render_delete_tab(words):
    if not words:
        st.info("삭제할 단어가 없습니다.")
        return

    word_options = {
        item.get("id"): f"#{item.get('id')} {item.get('word')} - {item.get('meaning')}"
        for item in words
    }
    selected_id = st.selectbox(
        "삭제할 단어",
        list(word_options),
        format_func=word_options.get,
    )
    if st.button("단어 삭제", type="secondary"):
        removed = delete_word(words, selected_id)
        save_vocab(words)
        st.success(f"'{removed['word']}' 단어를 삭제했습니다.")
        st.rerun()


def render_streamlit_app():
    st.set_page_config(page_title="영어 단어 암기", page_icon="📘", layout="wide")
    st.title("📘 영어 단어 암기")
    st.caption("Leitner Box 방식으로 영어 단어를 추가하고 복습하세요.")

    if "vocabulary" not in st.session_state:
        st.session_state.vocabulary = load_vocab()
    words = st.session_state.vocabulary
    summary = get_review_summary(words)

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("전체 단어", summary["total"])
    metric_col2.metric("오늘 복습", summary["due"])
    metric_col3.metric("완료한 Box", ", ".join(
        f"{box}: {count}" for box, count in summary["boxes"].items()
    ))

    add_tab, list_tab, review_tab, delete_tab = st.tabs(
        ["단어 추가", "전체 목록", "오늘 복습", "단어 삭제"]
    )
    with add_tab:
        render_add_tab(words)
    with list_tab:
        sorted_words = sorted(
            words,
            key=lambda item: (item.get("next_review") or "9999-12-31", item.get("id", 0)),
        )
        render_word_table(sorted_words, "전체 단어 목록")
    with review_tab:
        render_review_tab(words)
    with delete_tab:
        render_delete_tab(words)


def main(argv=None):
    if argv is None:
        render_streamlit_app()
        return

    args = build_parser().parse_args(argv)
    if args.command is None:
        interactive_menu()
        return

    if args.command == "add":
        words = load_vocab()
        item = add_word(words, args.word, args.meaning, args.example)
        save_vocab(words)
        print(f"저장 완료: #{item['id']} {item['word']} - {item['meaning']}")
        return

    if args.command == "list":
        words = load_vocab()
        list_words(words, review_due_only=args.due)
        return

    if args.command == "quiz":
        words = load_vocab()
        if args.word_id is not None:
            target = next((item for item in words if int(item.get("id", -1)) == args.word_id), None)
            if target is None:
                print(f"ID {args.word_id} 에 해당하는 단어가 없습니다.")
                return
            due_words = [target]
        else:
            due_words = get_due_words(words)
        if not due_words:
            print("오늘 복습할 항목이 없습니다.")
            return
        target = due_words[0]
        user_answer = input(f"[{target['id']}] '{target['word']}' 의 의미를 입력하세요: ").strip()
        is_correct = normalize_meaning(user_answer).lower() == normalize_meaning(target["meaning"]).lower()
        updated = process_quiz_result(target, is_correct)
        for index, item in enumerate(words):
            if item.get("id") == target.get("id"):
                words[index] = updated
                break
        save_vocab(words)
        if is_correct:
            print("정답입니다! ✅")
        else:
            print(f"오답입니다. 정답은 '{target['meaning']}' 입니다. ❌")
        return

    if args.command == "delete":
        words = load_vocab()
        try:
            delete_word(words, args.word_id)
            save_vocab(words)
            print(f"ID {args.word_id} 항목이 삭제되었습니다.")
        except ValueError as exc:
            print(f"삭제 실패: {exc}")
        return


if __name__ == "__main__":
    main()
