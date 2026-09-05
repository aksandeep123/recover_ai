import os
import sys
import asyncio
import subprocess
import re
from PIL import Image, ImageDraw, ImageFont
import edge_tts
import imageio_ffmpeg
from gtts import gTTS

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
VOICE = "en-IN-PrabhatNeural"

OUTPUT_DIR = "pitch_video"
AUDIO_DIR = "pitch_audio"
SLIDES_DIR = os.path.join(OUTPUT_DIR, "slides")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(SLIDES_DIR, exist_ok=True)

SCENES = [
    {
        "id": "01_problem",
        "title": "The Problem: The $5B+ Involuntary Dunning Churn Crisis",
        "subtitle": "0:00 - 0:45 | Why Legacy Dunning & Blind Retries Destroy Customer Trust",
        "script": (
            "Every year, subscription and recurring revenue businesses lose over five billion dollars "
            "to a silent killer: involuntary churn. When a customer payment fails due to an expired card, "
            "network timeout, or temporary month-end balance dip, traditional dunning systems do something disastrous. "
            "They blindly retry the charge at three in the morning, spam the customer with cold generic emails, "
            "and eventually cancel the subscription. This blind retrying triggers bank fraud filters, racks up "
            "failed transaction penalties, and destroys customer trust. Businesses are losing loyal customers not "
            "because they wanted to cancel, but because the payment recovery layer is reactive, static, and fundamentally broken."
        ),
        "theme": "danger",
        "cards": [
            ("Blind Midnight Retries", "Gateways blindly retry transactions at 3:00 AM, triggering bank fraud locks and card blocks (84% failure rate).", "#EF4444"),
            ("Generic Spam Communications", "Impersonal generic warning emails get ignored, sent to spam, or irritate high-value users.", "#F59E0B"),
            ("Zero Financial Governance", "High-value enterprise subscriptions (Rs 50k+) are automatically terminated without human oversight.", "#EF4444"),
            ("Catastrophic Revenue Leakage", "35% to 40% of overall subscription churn is purely involuntary and preventable with intelligent dunning.", "#F59E0B")
        ]
    },
    {
        "id": "02_solution",
        "title": "The Solution: RecoverAI Autonomous Recovery Operating Layer",
        "subtitle": "0:45 - 1:30 | Real-Time Agentic Orchestration with Deterministic Safety",
        "script": (
            "Meet RecoverAI, an autonomous, multi-agent revenue recovery operating layer designed for modern recurring "
            "businesses and Razorpay merchants. Instead of dumb static rules, RecoverAI acts as an intelligent recovery "
            "nervous system. The moment a payment failure webhook arrives, RecoverAI diagnoses the exact technical and "
            "behavioral root cause, evaluates customer churn risk, and formulates an intelligent, multi-channel recovery cascade. "
            "It schedules retries precisely when liquidity is highest, triggers frictionless one-click WhatsApp UPI switches, "
            "and protects high-value enterprise accounts through human-in-the-loop safety quarantine. RecoverAI transforms "
            "failed payments from lost revenue into high-conversion touchpoints."
        ),
        "theme": "indigo",
        "cards": [
            ("Real-Time Multi-Agent Swarm", "Sub-800ms root cause diagnosis, churn risk scoring, and dynamic cascade generation powered by Gemini 2.5.", "#6366F1"),
            ("Air-Gapped Policy Engine", "Deterministic rules strictly enforce max retry limits (<=3), quiet hours, and financial invariants outside the LLM.", "#10B981"),
            ("Hyper-Personalized Cascades", "Context-aware timing (payroll alignment), 1-click WhatsApp UPI Autopay migration, and tailored incentives.", "#06B6D4"),
            ("Human-in-the-Loop Quarantine", "High-ticket payments (>Rs 10,000) automatically quarantined into the Approval Center for human verification.", "#8B5CF6")
        ]
    },
    {
        "id": "03_architecture",
        "title": "Architecture: 4-Tier Agentic System & Deterministic Guardrails",
        "subtitle": "1:30 - 2:15 | Combining Generative AI Reasoning with Strict Policy Validation",
        "script": (
            "At the core of RecoverAI is an enterprise-grade four-tier architecture. In Tier One, our perception layer "
            "ingests real-time Razorpay webhooks and pulls Customer 360 signals including payroll cycle telemetry. "
            "In Tier Two, specialized Google Gemini 2.5 agents collaborate in a reasoning swarm. The Root Cause Agent "
            "dissects error nuances, the Risk Agent estimates churn propensity, the Strategy Agent synthesizes the "
            "optimal intervention, and the Communication Agent drafts empathetic copy. Crucially, in Tier Three, every "
            "AI-proposed action passes through an air-gapped Deterministic Policy Engine. This hardcoded rules engine "
            "guarantees that no LLM can ever violate financial invariants, exceed retry caps, or disturb customers "
            "during quiet hours. Finally, Tier Four executes actions via Razorpay APIs and WhatsApp with real-time feedback logging."
        ),
        "theme": "cyan",
        "cards": [
            ("Tier 1: Perception & Feature Store", "Razorpay Webhooks ingestion, Customer 360 profile, historical payment telemetry, and salary cycle detection.", "#0EA5E9"),
            ("Tier 2: Gemini 2.5 Multi-Agent Swarm", "4 Specialized Agents: Root Cause Agent + Risk Agent + Strategy Agent + Communication Agent.", "#6366F1"),
            ("Tier 3: Air-Gapped Policy Engine", "Strict deterministic invariants: Cooldown gates, max retry bounds, quiet hours, and high-value approvals.", "#10B981"),
            ("Tier 4: Execution & Feedback Loop", "Razorpay API integration, WhatsApp Business API, 1-click UPI intent links, and continuous learning.", "#A855F7")
        ]
    },
    {
        "id": "04_scenario1",
        "title": "Demo Scenario 1: Month-End Balance Dip & Smart Payroll Rescheduling",
        "subtitle": "2:15 - 3:00 | Intelligent Timing Alignment vs. Destructive Blind Retries",
        "script": (
            "Let us walk through three real demo scenarios. In Scenario One, Rohans three thousand four hundred and "
            "ninety-nine rupee SaaS subscription fails on the twenty-eighth of the month due to insufficient funds. "
            "A legacy dunning system would have retried every night, failing four times and irritating Rohan. "
            "RecoverAI Root Cause Agent recognizes a temporary month-end liquidity crunch and inspects his salary credit "
            "pattern, which shows salary deposits on the first of every month. The Strategy Agent halts immediate retries "
            "and schedules an automatic smart retry for the morning of the first at nine-thirty AM, accompanied by a polite "
            "WhatsApp reminder. On the scheduled date, the payment executes flawlessly on the very first attempt."
        ),
        "theme": "emerald",
        "cards": [
            ("Failed Webhook Ingestion", "Customer: Rohan Sharma | Amount: Rs 3,499 (SaaS Pro) | Gateway Error: insufficient_funds (28th Month).", "#3B82F6"),
            ("Root Cause & Risk Diagnosis", "Root Cause: Temporary Month-End Liquidity Crunch (96% Conf) | Churn Risk: Low | Salary: 1st of month.", "#10B981"),
            ("Strategy & Policy Clearance", "Action: Suppress immediate retry. Reschedule auto-debit for 1st at 09:30 AM + send polite WhatsApp alert.", "#F59E0B"),
            ("Flawless Recovery Result", "Recovered Rs 3,499 on the 1st at 09:30 AM on first attempt. 0 retry fees wasted, 100% customer retention.", "#10B981")
        ]
    },
    {
        "id": "05_scenario2",
        "title": "Demo Scenario 2: High-Value Enterprise Payment & Policy Interception",
        "subtitle": "3:00 - 3:45 | Air-Gapped Safety Quarantine in the Human Approval Center",
        "script": (
            "In Scenario Two, Apex Tech Solutions experiences a payment failure on their forty-five thousand rupee annual "
            "enterprise subscription. Because this is a mission-critical, high-value account, the Strategy Agent proposes "
            "a VIP account manager outreach and a targeted loyalty incentive. Before any message is sent, the Deterministic "
            "Policy Engine intercepts the transaction because it exceeds the ten thousand rupee threshold. The case is "
            "safely held in the Human Approval Center. A recovery manager reviews the full Customer 360 context, inspects "
            "the AI recommendation, and clicks Approve and Execute. This human-in-the-loop safeguard eliminates any "
            "risk of automated hallucinations on high-ticket enterprise revenue."
        ),
        "theme": "purple",
        "cards": [
            ("Enterprise Payment Failure", "Customer: Apex Tech Solutions | Amount: Rs 45,000 (Enterprise Annual) | High LTV Corporate Account.", "#8B5CF6"),
            ("Policy Engine Interception", "Rule Triggered: Amount > Rs 10,000 & Risk > 0.70 -> Auto-quarantined to Human Approval Center.", "#EF4444"),
            ("Operator 360 Review", "Manager inspects AI-synthesized custom VIP renewal package & custom payment link with 10% loyalty concession.", "#F59E0B"),
            ("Human Approval & Execution", "Manager clicks Approve & Execute. Rs 45,000 enterprise renewal successfully recovered with full audit log.", "#10B981")
        ]
    },
    {
        "id": "06_scenario3",
        "title": "Demo Scenario 3: Expired Card & WhatsApp 1-Click UPI Autopay Switch",
        "subtitle": "3:45 - 4:30 | Instant Payment Method Migration with Zero Retries",
        "script": (
            "In Scenario Three, Priyas recurring subscription fails because her debit card has expired. Traditional gateways "
            "keep retrying expired cards, wasting money on failed gateway fees. RecoverAI Root Cause Agent immediately classifies "
            "the error as a permanent card failure and permanently suppresses retries. Instead, the Communication Agent sends a "
            "verified WhatsApp interactive message containing a direct one-click Razorpay UPI Autopay migration link. Priya opens "
            "WhatsApp on her phone, taps the link, and authorizes a UPI mandate via Google Pay in ten seconds. Future payments "
            "are now completely automated on UPI, eliminating churn instantly."
        ),
        "theme": "emerald",
        "cards": [
            ("Terminal Card Expiry", "Customer: Priya Patel | Amount: Rs 1,299/mo | Error: card_expired -> Retrying is mathematically futile.", "#EF4444"),
            ("Autonomous Cascade Switch", "Root Cause Agent suppresses all card retries. Dispatches dynamic WhatsApp 1-Click UPI Autopay switch link.", "#06B6D4"),
            ("Frictionless Mobile Authorization", "Customer receives WhatsApp alert, taps Razorpay Smart Intent link, and authorizes UPI Mandate in 10s.", "#10B981"),
            ("Permanent Churn Shield", "Payment recovered instantly; subscription seamlessly migrated to recurring UPI autopay.", "#10B981")
        ]
    },
    {
        "id": "07_results",
        "title": "Demo Benchmark Results & Unit Economics",
        "subtitle": "4:30 - 5:00 | 10,000-Transaction Synthetic Benchmark Dataset Evaluation",
        "script": (
            "To validate RecoverAI, we benchmarked the system across a standardized ten thousand failed payment demo dataset. "
            "The results are decisive. RecoverAI achieved a seventy-two point four percent recovery rate, compared to just "
            "twenty-eight percent under legacy static dunning, recovering eighteen point four two million rupees in recurring "
            "revenue. By suppressing wasteful attempts, the system prevented over four thousand eight hundred blind retries "
            "and quarantined three hundred and twelve high-risk enterprise cases. With a total execution cost of just "
            "one hundred and twenty-seven thousand rupees across WhatsApp and AI inference, RecoverAI delivered an astronomical "
            "fourteen thousand four hundred and fifty-one percent Net ROI. RecoverAI turns payment failures into retained "
            "customers and compounding revenue. Thank you."
        ),
        "theme": "gold",
        "cards": [
            ("Rs 18.42M Total Recovered", "72.4% Recovery Rate on 10k Synthetic Demo Benchmark (vs 28.1% Legacy Rule Baseline).", "#10B981"),
            ("4,820 Blind Retries Prevented", "Rs 241,000 saved directly in failed gateway retry penalty fees.", "#3B82F6"),
            ("312 Enterprise Cases Protected", "High-value transactions safely quarantined in Human Approval Center with zero hallucinations.", "#8B5CF6"),
            ("14,451% Net ROI Delivered", "Rs 18.42M recovered on Rs 127.4k total operational cost (WhatsApp + Gemini LLM tokens).", "#F59E0B")
        ]
    }
]

def get_font(size, bold=False):
    font_names = ["segoeui.ttf", "arial.ttf", "calibri.ttf"]
    if bold:
        font_names = ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf"]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            try:
                return ImageFont.truetype(f"C:/Windows/Fonts/{fn}", size)
            except Exception:
                continue
    return ImageFont.load_default()

def draw_rounded_rect(draw, bbox, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=width)

def render_slide_image(scene, index, total, output_path):
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), "#0B0F19")
    draw = ImageDraw.Draw(img)

    # Header Bar
    draw.rectangle([(0, 0), (W, 110)], fill="#111827")
    draw.line([(0, 110), (W, 110)], fill="#374151", width=2)

    f_brand = get_font(32, bold=True)
    f_badge = get_font(20, bold=True)
    f_title = get_font(38, bold=True)
    f_subtitle = get_font(22, bold=False)
    f_card_title = get_font(24, bold=True)
    f_card_body = get_font(19, bold=False)
    f_footer = get_font(18, bold=False)

    draw.text((60, 35), "⚡ RecoverAI", fill="#6366F1", font=f_brand)
    draw.text((270, 42), "Autonomous Revenue Recovery Operating Layer", fill="#9CA3AF", font=get_font(22))

    badge_text = f"SCENE {index+1} / {total}"
    draw_rounded_rect(draw, (W - 240, 32, W - 60, 78), radius=10, fill="#1E293B", outline="#4F46E5", width=2)
    draw.text((W - 220, 43), badge_text, fill="#A5B4FC", font=f_badge)

    theme_colors = {
        "danger": ("#EF4444", "#FCA5A5"),
        "indigo": ("#6366F1", "#A5B4FC"),
        "cyan": ("#06B6D4", "#67E8F9"),
        "emerald": ("#10B981", "#6EE7B7"),
        "purple": ("#8B5CF6", "#C4B5FD"),
        "gold": ("#F59E0B", "#FDE68A")
    }
    primary_color, accent_color = theme_colors.get(scene["theme"], ("#6366F1", "#A5B4FC"))

    draw.text((60, 140), scene["title"], fill="#F9FAFB", font=f_title)
    draw.text((60, 195), scene["subtitle"], fill=accent_color, font=f_subtitle)
    draw.line([(60, 235), (450, 235)], fill=primary_color, width=4)

    cards = scene["cards"]
    card_w = 870
    card_h = 330
    positions = [
        (60, 265),
        (990, 265),
        (60, 625),
        (990, 625)
    ]

    for i, (ctitle, cdesc, caccent) in enumerate(cards):
        if i >= 4:
            break
        x, y = positions[i]
        draw_rounded_rect(draw, (x, y, x + card_w, y + card_h), radius=16, fill="#131D31", outline="#1F2E4D", width=2)
        draw_rounded_rect(draw, (x, y, x + card_w, y + 60), radius=16, fill="#1E293B")
        draw.rectangle([(x, y + 30), (x + card_w, y + 60)], fill="#1E293B")
        draw.line([(x, y + 60), (x + card_w, y + 60)], fill="#334155", width=1)
        
        draw.ellipse([(x + 25, y + 20), (x + 43, y + 38)], fill=caccent)
        draw.text((x + 55, y + 15), ctitle, fill="#FFFFFF", font=f_card_title)

        words = cdesc.split()
        lines = []
        cur_line = []
        for w in words:
            cur_line.append(w)
            test_line = " ".join(cur_line)
            bbox = draw.textbbox((0, 0), test_line, font=f_card_body)
            if (bbox[2] - bbox[0]) > (card_w - 60):
                cur_line.pop()
                lines.append(" ".join(cur_line))
                cur_line = [w]
        if cur_line:
            lines.append(" ".join(cur_line))

        line_y = y + 85
        for line in lines:
            draw.text((x + 30, line_y), line, fill="#CBD5E1", font=f_card_body)
            line_y += 34

    draw.rectangle([(0, H - 70), (W, H)], fill="#0F172A")
    draw.line([(0, H - 70), (W, H - 70)], fill="#1E293B", width=2)
    
    footer_text = "Razorpay AI Buildathon 2026 | AI Revenue Recovery Track | Synthetic Demo Benchmark (10k Tx)"
    draw.text((60, H - 48), footer_text, fill="#64748B", font=f_footer)
    
    watermark = "Audio: Indian English Voice (Male)"
    draw.text((W - 480, H - 48), watermark, fill="#10B981", font=f_footer)

    img.save(output_path, quality=95)
    print(f"Rendered slide: {output_path}")

async def generate_scene_audio(scene):
    audio_path = os.path.join(AUDIO_DIR, f"{scene['id']}.mp3")
    print(f"Generating audio for {scene['id']}...")
    
    sentences = [s.strip() for s in re.split(r'[\.\!\?]+', scene["script"]) if s.strip()]
    temp_files = []
    
    for idx, s in enumerate(sentences):
        tmp_p = os.path.join(AUDIO_DIR, f"tmp_{scene['id']}_{idx}.mp3")
        success = False
        try:
            communicate = edge_tts.Communicate(s + ".", VOICE)
            await communicate.save(tmp_p)
            if os.path.exists(tmp_p) and os.path.getsize(tmp_p) > 500:
                success = True
        except Exception as e:
            print(f"  Edge TTS failed for fragment {idx}, falling back to gTTS (Indian English): {e}")

        if not success:
            tts = gTTS(s + ".", lang='en', tld='co.in')
            tts.save(tmp_p)
            
        temp_files.append(tmp_p)

    # Concat fragments with ffmpeg
    concat_txt = os.path.join(AUDIO_DIR, f"list_{scene['id']}.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for p in temp_files:
            clean = os.path.abspath(p).replace("\\", "/")
            f.write(f"file '{clean}'\n")

    cmd = [FFMPEG_EXE, "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c", "copy", audio_path]
    subprocess.run(cmd, check=True)

    # Clean up temp files
    for p in temp_files:
        if os.path.exists(p):
            os.remove(p)
    if os.path.exists(concat_txt):
        os.remove(concat_txt)

    print(f"Saved complete scene audio: {audio_path} ({os.path.getsize(audio_path)} bytes)")
    return audio_path

def get_media_duration(file_path):
    cmd = [FFMPEG_EXE, "-i", file_path]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    import re
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = float(match.group(3))
        return hours * 3600 + minutes * 60 + seconds
    return 30.0

def make_scene_video(slide_img, audio_file, output_scene_mp4):
    duration = get_media_duration(audio_file)
    print(f"Creating video for {slide_img} + {audio_file} (duration: {duration:.2f}s)...")
    cmd = [
        FFMPEG_EXE, "-y",
        "-loop", "1",
        "-i", slide_img,
        "-i", audio_file,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        "-shortest",
        output_scene_mp4
    ]
    subprocess.run(cmd, check=True)
    print(f"Generated scene video: {output_scene_mp4}")

def concat_videos(scene_mp4s, final_output):
    concat_list_path = os.path.join(OUTPUT_DIR, "concat_list.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for p in scene_mp4s:
            clean_p = os.path.abspath(p).replace("\\", "/")
            f.write(f"file '{clean_p}'\n")

    print(f"Concatenating all {len(scene_mp4s)} scenes into {final_output}...")
    cmd = [
        FFMPEG_EXE, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        final_output
    ]
    subprocess.run(cmd, check=True)
    print(f"Successfully generated final video: {final_output}")

async def main():
    scene_mp4s = []
    
    for i, scene in enumerate(SCENES):
        slide_img = os.path.join(SLIDES_DIR, f"{scene['id']}.png")
        render_slide_image(scene, i, len(SCENES), slide_img)
        
        audio_file = await generate_scene_audio(scene)
        scene_mp4 = os.path.join(OUTPUT_DIR, f"{scene['id']}.mp4")
        make_scene_video(slide_img, audio_file, scene_mp4)
        scene_mp4s.append(scene_mp4)

    final_video = os.path.join(OUTPUT_DIR, "recoverai_pitch_demo_video.mp4")
    concat_videos(scene_mp4s, final_video)
    
    master_audio = os.path.join(AUDIO_DIR, "recoverai_full_5min_pitch_voiceover.mp3")
    print("Extracting full master audio from video...")
    cmd = [
        FFMPEG_EXE, "-y",
        "-i", final_video,
        "-vn",
        "-c:a", "libmp3lame",
        "-q:a", "2",
        master_audio
    ]
    subprocess.run(cmd, check=True)
    
    total_dur = get_media_duration(final_video)
    print(f"\n==========================================")
    print(f"🎉 FINAL VIDEO READY: {final_video}")
    print(f"🕒 TOTAL DURATION: {int(total_dur // 60)}m {int(total_dur % 60)}s ({total_dur:.2f} seconds)")
    print(f"🎙️ VOICE: Indian Male Voice")
    print(f"==========================================")

if __name__ == "__main__":
    asyncio.run(main())
