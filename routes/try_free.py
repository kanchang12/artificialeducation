import os
from flask import Blueprint, jsonify, request
from google import genai

try_free_bp = Blueprint("try_free", __name__)


def get_gemini():
    return genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))


# Correct answers and grading context live server-side only — never sent to the client.
QUESTIONS = [
    {
        "type": "mcq",
        "q": "Which parameter mainly controls how random or creative an LLM's output is?",
        "options": ["Temperature", "Token limit", "Embedding size", "Latency"],
        "correct": 0,
    },
    {
        "type": "mcq",
        "q": "Your RAG chatbot's vector index was built last month. A new pricing page was added to "
             "the docs folder this morning. A customer asks about today's price and gets yesterday's "
             "answer, even though the new page is sitting right there in the docs folder. What's missing?",
        "options": [
            "The new document was never chunked, embedded, and added to the vector index",
            "The temperature is set too low",
            "The prompt needs more few-shot examples",
            "The model needs to be upgraded to a bigger one",
        ],
        "correct": 0,
    },
    {
        "type": "dragdrop",
        "q": "Put these RAG pipeline steps in the correct order:",
        "items": [
            "Generate the answer grounded in the retrieved context",
            "Chunk the source documents, usually with some overlap",
            "Embed each chunk and store the vectors in a vector database",
            "Embed the incoming query and retrieve the top-k most similar chunks",
        ],
        "correct": [1, 2, 3, 0],
    },
    {
        "type": "dropdown",
        "q": "Embeddings are high-dimensional vectors. Cosine similarity measures the",
        "blankSuffix": "between two vectors — not how long either vector is.",
        "options": ["angle", "magnitude", "color", "distance"],
        "correct": "angle",
    },
    {
        "type": "prompt",
        "q": "Write a system prompt for a support AI that should answer only from a provided knowledge "
             "base, refuse anything outside it, and stay friendly.",
        "hint": "There's no single right answer — we're checking that you think like a prompt engineer.",
        "minLength": 25,
    },
]


def public_questions():
    """Strip correct answers before sending to the client."""
    out = []
    for q in QUESTIONS:
        clean = {"type": q["type"], "q": q["q"]}
        if q["type"] == "mcq":
            clean["options"] = q["options"]
        elif q["type"] == "dragdrop":
            clean["items"] = q["items"]
        elif q["type"] == "dropdown":
            clean["options"] = q["options"]
            clean["blankSuffix"] = q["blankSuffix"]
        elif q["type"] == "prompt":
            clean["hint"] = q["hint"]
            clean["minLength"] = q["minLength"]
        out.append(clean)
    return out


@try_free_bp.route("/api/try-free/questions", methods=["GET", "POST"])
def try_free_questions():
    return jsonify({"ok": True, "questions": public_questions()})


@try_free_bp.route("/api/try-free/check", methods=["GET", "POST"])
def try_free_check():
    data = request.get_json(force=True, silent=True) or {}
    idx = data.get("index")
    answer = data.get("answer")

    if idx is None or not isinstance(idx, int) or idx < 0 or idx >= len(QUESTIONS):
        return jsonify({"ok": False, "error": "Invalid question index"}), 400

    q = QUESTIONS[idx]
    correct = None
    grading_context = ""

    if q["type"] == "mcq":
        if not isinstance(answer, int) or answer < 0 or answer >= len(q["options"]):
            return jsonify({"ok": False, "error": "Invalid answer"}), 400
        correct = (answer == q["correct"])
        grading_context = (
            f"Question: {q['q']}\nOptions: {q['options']}\n"
            f"Correct answer: {q['options'][q['correct']]}\n"
            f"Student selected: {q['options'][answer]}"
        )
    elif q["type"] == "dropdown":
        if not isinstance(answer, str):
            return jsonify({"ok": False, "error": "Invalid answer"}), 400
        correct = (answer == q["correct"])
        grading_context = (
            f"Question (fill the blank): {q['q']} ___ {q['blankSuffix']}\n"
            f"Correct word: {q['correct']}\nStudent chose: {answer}"
        )
    elif q["type"] == "dragdrop":
        if not isinstance(answer, list) or sorted(answer) != list(range(len(q["items"]))):
            return jsonify({"ok": False, "error": "Invalid answer"}), 400
        correct = (answer == q["correct"])
        correct_order = " → ".join(q["items"][i] for i in q["correct"])
        student_order = " → ".join(q["items"][i] for i in answer)
        grading_context = (
            f"Question: {q['q']}\nCorrect order: {correct_order}\nStudent's order: {student_order}"
        )
    elif q["type"] == "prompt":
        if not isinstance(answer, str) or len(answer.strip()) < q["minLength"]:
            return jsonify({"ok": False, "error": "Answer too short"}), 400
        grading_context = f"Task: {q['q']}\nStudent's system prompt:\n{answer.strip()}"
    else:
        return jsonify({"ok": False, "error": "Unknown question type"}), 400

    feedback = gemini_feedback(q["type"], grading_context, correct)
    return jsonify({"ok": True, "correct": correct, "feedback": feedback})


def gemini_feedback(qtype, grading_context, correct):
    if not os.environ.get("GEMINI_API_KEY"):
        return "Gemini grading is offline right now — try again in a moment."

    if qtype == "prompt":
        system = (
            "You are a senior prompt engineer reviewing a junior engineer's system prompt, "
            "like a quick PR comment. Be specific and technical, 3-5 sentences. Call out what's "
            "missing — scope boundary, refusal behavior, tone instruction, format constraints — "
            "and what's good. No generic filler, no 'great job!' padding."
        )
    else:
        verdict = "correct" if correct else "incorrect"
        system = (
            f"You are an AI engineering instructor giving instant feedback on a quiz question. "
            f"The student's answer was {verdict}. Be specific and technical, 3-5 sentences. "
            "If correct, confirm briefly and add one sharper technical detail they likely don't know yet. "
            "If incorrect, explain precisely why their specific choice is wrong and what the correct "
            "concept actually is. No generic filler, no restating the question."
        )

    try:
        client = get_gemini()
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=grading_context,
            config={"system_instruction": system, "max_output_tokens": 2300},
        )
        return response.text
    except Exception as e:
        return f"Couldn't reach Gemini for detailed feedback ({e}). Your answer was recorded."
