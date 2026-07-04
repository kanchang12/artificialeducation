from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request
from data_loader import get_lab, load_labs
from routes.auth import require_login
import os
from google import genai

labs_bp = Blueprint("labs", __name__)

def get_gemini():
    return genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

@labs_bp.route("/lab/<task_id>")
@require_login
def lab_detail(task_id):
    lab = get_lab(task_id)
    if not lab:
        return redirect(url_for("main.dashboard"))
    if lab.get("difficulty") == "legend":
        from supabase_client import get_profile
        profile = get_profile(session["user_id"])
        if profile:
            session["credits_minutes"] = float(profile.get("credits_minutes", 0) or 0)
        if float(session.get("credits_minutes", 0) or 0) <= 0:
            return redirect(url_for("main.upgrade_page"))
    all_labs = load_labs()
    idx = next((i for i, l in enumerate(all_labs) if l.get("task_id") == task_id), 0)
    prev_lab = all_labs[idx - 1] if idx > 0 else None
    next_lab = all_labs[idx + 1] if idx < len(all_labs) - 1 else None
    return render_template("lab.html", lab=lab, prev_lab=prev_lab, next_lab=next_lab,
                           user_name=session.get("user_name", ""))

@labs_bp.route("/api/lab/ask", methods=["GET", "POST"])
@require_login
def lab_ask():
    data = request.get_json(force=True, silent=True) or {}
    task_id = data.get("task_id", "")
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"ok": False, "error": "No question provided"}), 400
    lab = get_lab(task_id)
    if not lab:
        return jsonify({"ok": False, "error": "Lab not found"}), 404

    if not os.environ.get("GEMINI_API_KEY"):
        return jsonify({"ok": False, "error": "GEMINI_API_KEY not set"}), 503

    system = f"""You are an AI/ML engineering tutor helping students learn practical AI development.
The student is working on this lab:
Title: {lab['title']}
Topic: {lab['topic']}
Problem: {lab['problem']}
Context: {lab.get('context', '')}

Guide the student with clear, concise answers. Don't give away the full solution — use the Socratic method.
Keep responses under 200 words. Be encouraging and practical."""

    try:
        client = get_gemini()
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=question,
            config={"system_instruction": system, "max_output_tokens": 2300}
        )
        return jsonify({"ok": True, "answer": response.text})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@labs_bp.route("/api/lab/check", methods=["GET", "POST"])
@require_login
def lab_check():
    data = request.get_json(force=True, silent=True) or {}
    task_id = data.get("task_id", "")
    answer = data.get("answer", "").strip()
    if not answer:
        return jsonify({"ok": False, "error": "No answer provided"}), 400
    lab = get_lab(task_id)
    if not lab:
        return jsonify({"ok": False, "error": "Lab not found"}), 404

    if not os.environ.get("GEMINI_API_KEY"):
        return jsonify({"ok": False, "error": "GEMINI_API_KEY not set"}), 503

    system = f"""You are an AI engineering instructor grading a student answer.

Lab: {lab['title']}
Problem: {lab['problem']}
Expert solution: {lab['solution']}

Grade the student's answer on a scale of 1-10.
Respond in this exact format:
SCORE: <number>
FEEDBACK: <2-4 sentences of specific, constructive feedback. What they got right, what they missed, what to improve.>

Be honest but encouraging. Focus on the concepts, not writing style."""

    try:
        client = get_gemini()
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=f"Student answer: {answer}",
            config={"system_instruction": system, "max_output_tokens": 2300}
        )
        text = response.text
        score = 5
        feedback = text
        for line in text.split("\n"):
            if line.startswith("SCORE:"):
                try:
                    score = int(line.replace("SCORE:", "").strip())
                except:
                    pass
            if line.startswith("FEEDBACK:"):
                feedback = line.replace("FEEDBACK:", "").strip()

        stars = "⭐" * min(score, 10)
        color = "#065f46" if score >= 7 else "#92400e" if score >= 4 else "#991b1b"
        html = f'<div style="font-weight:700;color:{color};margin-bottom:0.5rem;">{stars} Score: {score}/10</div><p>{feedback}</p>'
        return jsonify({"ok": True, "feedback": html, "score": score})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
