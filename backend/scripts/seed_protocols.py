"""
Seed the database with health protocols and policies.
Run once: python -m scripts.seed_protocols  (from the backend/ directory)
Also called automatically on server startup if the protocols table is empty.
"""
from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal, init_db
from app.models import Protocol

PROTOCOLS = [
    {
        "title": "Fever Management",
        "category": "symptom",
        "priority": 10,
        "keywords": [
            "fever", "temperature", "bukhar", "high temp", "febrile",
            "100 degree", "101", "102", "103", "104", "sweating", "chills",
        ],
        "content": (
            "Mild fever (99–101°F / 37.2–38.3°C): encourage rest, fluids (ORS, coconut water, warm dal water), "
            "light meals. Paracetamol (500–1000 mg for adults) every 6 hours if uncomfortable — do not exceed 4 g/day.\n"
            "Moderate fever (101–103°F): same + lukewarm sponging on forehead and armpits. Monitor closely.\n"
            "High / persistent fever (>103°F or lasting >3 days): refer to a doctor promptly.\n"
            "Red flags → emergency: fever with stiff neck, rash, confusion, difficulty breathing, febrile convulsions in children."
        ),
    },
    {
        "title": "Headache & Migraine",
        "category": "symptom",
        "priority": 8,
        "keywords": [
            "headache", "head pain", "head ache", "migraine", "sir dard",
            "throbbing head", "temple pain", "forehead pain",
        ],
        "content": (
            "Tension headache: rest in a quiet, dark room; cold/warm compress on forehead; "
            "stay hydrated; paracetamol or ibuprofen if needed.\n"
            "Migraine: lie down in a dark, quiet room; cold pack; avoid triggers (strong light, noise, certain foods). "
            "Sumatriptan or prescribed medication if available.\n"
            "Lifestyle: reduce screen time, improve sleep, manage stress, stay hydrated.\n"
            "Red flags → emergency: sudden severe 'thunderclap' headache, headache with fever + stiff neck, "
            "headache after head injury, vision changes, weakness, or confusion."
        ),
    },
    {
        "title": "Cold, Cough & Sore Throat",
        "category": "symptom",
        "priority": 8,
        "keywords": [
            "cold", "cough", "runny nose", "blocked nose", "sneezing", "congestion",
            "sore throat", "throat pain", "throat ache", "flu", "phlegm", "mucus",
        ],
        "content": (
            "Rest and stay well-hydrated (warm water, herbal tea, kadha).\n"
            "Sore throat: warm salt-water gargles 3–4×/day; honey in warm water or ginger tea.\n"
            "Congestion: steam inhalation 2×/day; saline nasal drops.\n"
            "Dry cough: honey + ginger; avoid cold drinks and dusty environments.\n"
            "OTC options: antihistamines for runny nose; paracetamol for fever/pain.\n"
            "See a doctor if: fever >101°F, symptoms worsen after 7 days, severe chest pain, or difficulty breathing."
        ),
    },
    {
        "title": "Stomach Ache, Acidity & Digestion",
        "category": "symptom",
        "priority": 9,
        "keywords": [
            "stomach ache", "stomach pain", "stomach", "acidity", "acid reflux", "heartburn",
            "gas", "bloating", "indigestion", "nausea", "vomiting", "diarrhoea", "diarrhea",
            "loose motions", "constipation", "pet dard", "ulcer", "gastritis",
        ],
        "content": (
            "Acidity / heartburn: small frequent meals; avoid spicy, oily food and caffeine; "
            "cold milk or antacid (Gelusil/Digene) for quick relief; don't lie down immediately after eating.\n"
            "Gas / bloating: warm water with ajwain (carom seeds) or ginger; light walk after meals; avoid carbonated drinks.\n"
            "Diarrhoea: ORS after every loose stool; BRAT diet (banana, rice, applesauce, toast); "
            "avoid dairy and spicy food. If >5 stools/day or blood in stool → see a doctor.\n"
            "Nausea/vomiting: small sips of cold water or ORS; ginger tea; light meals when stable.\n"
            "Red flags: severe / worsening abdominal pain, blood in stool or vomit, signs of dehydration, "
            "fever with abdominal pain → emergency / doctor visit."
        ),
    },
    {
        "title": "Diabetes Management",
        "category": "chronic",
        "priority": 9,
        "keywords": [
            "diabetes", "diabetic", "blood sugar", "sugar level", "hba1c", "insulin",
            "glucose", "fasting sugar", "pp sugar", "metformin", "hypoglycemia",
            "low sugar", "high sugar", "hyperglycemia",
        ],
        "content": (
            "Daily monitoring: check fasting and post-meal glucose as advised by your doctor. "
            "Target fasting: 80–130 mg/dL; post-meal (2h): <180 mg/dL.\n"
            "Diet: complex carbs (daliya, brown rice, roti), high fibre, avoid sugar and refined carbs; "
            "small frequent meals; limit fruit juice.\n"
            "Exercise: 30-minute brisk walk 5 days/week lowers blood sugar significantly.\n"
            "Medication: take as prescribed; never skip insulin or oral tablets without consulting your doctor.\n"
            "Hypoglycemia (sugar <70): immediately take 15 g fast-acting sugar (3–4 glucose tablets, "
            "half cup juice, 1 tablespoon honey). Recheck after 15 min. If unconscious → emergency.\n"
            "Regular checkups: HbA1c every 3 months; eye, kidney, and foot exams annually."
        ),
    },
    {
        "title": "Blood Pressure (Hypertension / Hypotension)",
        "category": "chronic",
        "priority": 9,
        "keywords": [
            "blood pressure", "bp", "hypertension", "high blood pressure", "low bp",
            "low blood pressure", "hypotension", "bp high", "bp low", "dizziness",
            "light headed", "systolic", "diastolic",
        ],
        "content": (
            "High BP (hypertension): reduce salt (< 5 g/day); eat potassium-rich foods (banana, leafy greens); "
            "no smoking or heavy alcohol; 30 min aerobic exercise daily; manage stress with yoga/meditation. "
            "Take prescribed medication consistently — never stop abruptly.\n"
            "Low BP (hypotension): increase fluid and moderate salt intake; rise slowly from sitting/lying; "
            "compression stockings if advised; small frequent meals.\n"
            "Monitor: home BP log; target <130/80 mmHg for most adults.\n"
            "Red flags for high BP: BP >180/120, severe headache, blurry vision, chest pain → emergency."
        ),
    },
    {
        "title": "Sleep Problems & Fatigue",
        "category": "lifestyle",
        "priority": 7,
        "keywords": [
            "sleep", "insomnia", "can't sleep", "sleepless", "tired", "fatigue",
            "exhausted", "low energy", "always sleepy", "oversleeping", "sleep hygiene",
            "wake up at night",
        ],
        "content": (
            "Sleep hygiene: fixed wake and sleep times (even weekends); no screens 1 hour before bed; "
            "keep room dark, cool, quiet.\n"
            "Wind-down routine: warm shower, light stretching or reading; avoid caffeine after 2 pm.\n"
            "If mind races: 4-7-8 breathing (inhale 4s, hold 7s, exhale 8s); write worries in a journal.\n"
            "Fatigue: rule out anaemia, thyroid issues, or vitamin D / B12 deficiency with a blood test "
            "if it persists > 2 weeks.\n"
            "Avoid long daytime naps (>20 min); regular moderate exercise improves sleep quality.\n"
            "See a doctor if: insomnia >3 nights/week for > 1 month, or sleep apnoea signs (snoring, gasping)."
        ),
    },
    {
        "title": "Weight Management & Nutrition",
        "category": "lifestyle",
        "priority": 7,
        "keywords": [
            "weight", "fat", "obesity", "overweight", "lose weight", "weight loss",
            "diet", "calories", "bmi", "belly fat", "slim", "exercise", "nutrition",
        ],
        "content": (
            "Sustainable approach: aim for 0.5–1 kg/week loss; avoid crash diets.\n"
            "Diet: balanced plate (50% vegetables, 25% protein, 25% complex carbs); "
            "eat mindfully and slowly; avoid processed and fried foods; limit sugar.\n"
            "Hydration: 8–10 glasses of water/day; drink a glass before meals to reduce hunger.\n"
            "Exercise: 150 min moderate cardio + 2 strength sessions per week is the gold standard.\n"
            "Indian-specific tips: reduce maida (white flour), white rice, and packaged snacks; "
            "use mustard/olive oil in moderation; dals and paneer are great protein sources.\n"
            "Consult a dietician for a personalised plan, especially with diabetes or thyroid conditions."
        ),
    },
    {
        "title": "Stress, Anxiety & Mental Wellbeing",
        "category": "mental_health",
        "priority": 8,
        "keywords": [
            "stress", "anxiety", "anxious", "depression", "depressed", "sad",
            "worried", "mental health", "panic", "panic attack", "overthinking",
            "burnout", "mood", "crying", "hopeless",
        ],
        "content": (
            "Acknowledge and validate: it's okay to not be okay.\n"
            "Quick relief: box breathing (4-4-4-4), 5-4-3-2-1 grounding technique, "
            "cold water on face to calm the nervous system.\n"
            "Daily habits: 20–30 min walk/exercise; journalling; limiting news and social media; "
            "connecting with friends/family; adequate sleep.\n"
            "For persistent low mood: consider speaking to a counsellor or psychologist. "
            "In India: iCall (9152987821), Vandrevala Foundation (1860-2662-345) — free helplines.\n"
            "Red flags → seek help immediately: thoughts of self-harm, inability to function day-to-day, "
            "or suicidal ideation. Encourage professional support compassionately, without stigma."
        ),
    },
    {
        "title": "Refund, Subscription & Support Policy",
        "category": "policy",
        "priority": 5,
        "keywords": [
            "refund", "cancel", "cancellation", "subscription", "payment", "charge",
            "money back", "billing", "unsubscribe", "plan", "pricing",
        ],
        "content": (
            "Refund policy: Curelink offers a 7-day full refund from the date of purchase for new subscribers. "
            "After 7 days, refunds are evaluated case-by-case.\n"
            "To request a refund or cancel your subscription: contact support at support@curelink.in "
            "or use the in-app help section.\n"
            "Response time: support team typically responds within 24 business hours.\n"
            "For urgent billing issues, please email with subject line 'Urgent Billing – [your registered email]'."
        ),
    },
    {
        "title": "Back Pain & Joint Pain",
        "category": "symptom",
        "priority": 7,
        "keywords": [
            "back pain", "back ache", "lower back", "upper back", "joint pain",
            "knee pain", "shoulder pain", "neck pain", "arthritis", "spine",
            "slip disc", "sciatica",
        ],
        "content": (
            "Acute back pain (< 4 weeks): rest for 1–2 days max then gradually resume activity; "
            "hot/cold packs; ibuprofen or paracetamol; avoid heavy lifting.\n"
            "Posture: lumbar support while sitting; monitor at eye level; take breaks every 45 min.\n"
            "Exercises: cat-cow stretch, child's pose, pelvic tilts — gentle and daily.\n"
            "Joint pain: anti-inflammatory diet (turmeric, omega-3); low-impact exercise (swimming, yoga).\n"
            "See a doctor if: pain radiates down the leg, causes numbness/tingling, follows an injury, "
            "or doesn't improve after 2–3 weeks."
        ),
    },
    {
        "title": "Women's Health — Periods & Hormonal Health",
        "category": "women_health",
        "priority": 8,
        "keywords": [
            "periods", "menstruation", "period pain", "cramps", "irregular periods",
            "pcod", "pcos", "hormones", "menopause", "spotting", "heavy bleeding",
            "period late", "missed period",
        ],
        "content": (
            "Period cramps: heating pad on lower abdomen; ibuprofen (better than paracetamol for cramps); "
            "light exercise like walking; avoid caffeine and salty foods.\n"
            "Irregular periods: track cycle length for 3 months; common causes include stress, weight changes, "
            "thyroid issues, and PCOS.\n"
            "PCOS: low-GI diet, regular exercise, and weight management significantly improve symptoms. "
            "Consult a gynaecologist for medication (OCP, metformin).\n"
            "Heavy bleeding (soaking a pad/tampon every hour for 2+ hours) → see a doctor soon.\n"
            "Missed period with possible pregnancy → take a home test first, then consult a doctor."
        ),
    },
]


def seed():
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(Protocol).count()
        if existing > 0:
            print(f"Protocols table already has {existing} rows — skipping seed.")
            return

        for p in PROTOCOLS:
            db.add(Protocol(**p))
        db.commit()
        print(f"Seeded {len(PROTOCOLS)} protocols successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
