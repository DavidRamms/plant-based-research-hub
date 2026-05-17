"""
Configuration for the Plant-Based Research Hub.
"""

TOPICS = {
    "cardiovascular": {
        "name": "Cardiovascular Health",
        "description": "Effects of plant-based diets on heart disease, blood pressure, cholesterol, and cardiovascular outcomes.",
        "queries": [
            (
                '("plant-based diet" OR "vegan diet" OR "vegetarian diet" OR "whole food plant-based" OR "WFPB" OR "meat-free")'
                ' AND ("cardiovascular disease" OR "heart disease" OR "coronary artery disease" OR "blood pressure" OR "hypertension"'
                ' OR "cholesterol" OR "LDL" OR "atherosclerosis" OR "myocardial infarction" OR "stroke")'
            ),
            (
                '("reduced meat" OR "meat reduction" OR "red meat reduction" OR "less animal products" OR "plant-forward")'
                ' AND ("cardiovascular disease" OR "heart disease" OR "coronary artery disease" OR "blood pressure" OR "hypertension"'
                ' OR "cholesterol" OR "LDL" OR "atherosclerosis" OR "myocardial infarction" OR "stroke")'
            ),
        ],
    },
    "cancer": {
        "name": "Cancer Risk",
        "description": "Associations between plant-based diets and cancer incidence, progression, and mortality.",
        "queries": [
            (
                '("plant-based diet" OR "vegan diet" OR "vegetarian diet" OR "whole food plant-based" OR "WFPB" OR "meat-free")'
                ' AND ("cancer risk" OR "cancer incidence" OR "tumor" OR "colorectal cancer" OR "breast cancer" OR "prostate cancer"'
                ' OR "cancer mortality" OR "oncology" OR "carcinogenesis")'
            ),
            (
                '("red meat" OR "processed meat" OR "animal product reduction" OR "meat reduction")'
                ' AND ("cancer risk" OR "cancer incidence" OR "colorectal cancer" OR "breast cancer" OR "prostate cancer"'
                ' OR "cancer mortality" OR "carcinogenesis")'
            ),
        ],
    },
    "diabetes": {
        "name": "Type 2 Diabetes & Insulin Sensitivity",
        "description": "Impact of plant-based diets on blood glucose, insulin resistance, and type 2 diabetes prevention and management.",
        "queries": [
            (
                '("plant-based diet" OR "vegan diet" OR "vegetarian diet" OR "whole food plant-based" OR "WFPB" OR "meat-free")'
                ' AND ("type 2 diabetes" OR "insulin resistance" OR "insulin sensitivity" OR "blood glucose" OR "HbA1c"'
                ' OR "glycemic control" OR "diabetes prevention" OR "metabolic syndrome")'
            ),
            (
                '("reduced meat" OR "meat reduction" OR "low animal protein" OR "plant protein")'
                ' AND ("type 2 diabetes" OR "insulin resistance" OR "insulin sensitivity" OR "blood glucose" OR "HbA1c"'
                ' OR "glycemic control" OR "diabetes prevention")'
            ),
        ],
    },
    "bone_density": {
        "name": "Bone Density & Fracture Risk",
        "description": "Relationship between plant-based diets and bone mineral density, fracture risk, and skeletal health.",
        "queries": [
            (
                '("plant-based diet" OR "vegan diet" OR "vegetarian diet" OR "whole food plant-based" OR "WFPB" OR "meat-free")'
                ' AND ("bone density" OR "bone mineral density" OR "BMD" OR "fracture risk" OR "osteoporosis" OR "osteopenia"'
                ' OR "calcium absorption" OR "skeletal health")'
            ),
            (
                '("dairy-free" OR "dairy elimination" OR "no dairy" OR "low dairy" OR "animal protein reduction")'
                ' AND ("bone density" OR "bone mineral density" OR "BMD" OR "fracture risk" OR "osteoporosis"'
                ' OR "calcium absorption")'
            ),
        ],
    },
    "gut_microbiome": {
        "name": "Gut Microbiome",
        "description": "Effects of plant-based diets on gut microbiota composition, diversity, and intestinal health.",
        "queries": [
            (
                '("plant-based diet" OR "vegan diet" OR "vegetarian diet" OR "whole food plant-based" OR "WFPB" OR "meat-free")'
                ' AND ("gut microbiome" OR "gut microbiota" OR "intestinal microbiota" OR "microbial diversity"'
                ' OR "short-chain fatty acids" OR "SCFA" OR "gut health" OR "dysbiosis")'
            ),
            (
                '("reduced meat" OR "meat reduction" OR "animal product reduction" OR "high fiber diet")'
                ' AND ("gut microbiome" OR "gut microbiota" OR "intestinal microbiota" OR "microbial diversity"'
                ' OR "short-chain fatty acids" OR "gut health")'
            ),
        ],
    },
    "protein_muscle": {
        "name": "Protein Adequacy & Muscle Mass",
        "description": "Research on plant protein quality, amino acid profiles, muscle mass maintenance, and athletic performance on plant-based diets.",
        "queries": [
            (
                '("plant-based diet" OR "vegan diet" OR "vegetarian diet" OR "whole food plant-based" OR "WFPB" OR "meat-free")'
                ' AND ("protein adequacy" OR "muscle mass" OR "lean body mass" OR "muscle protein synthesis"'
                ' OR "plant protein" OR "amino acid" OR "athletic performance" OR "sarcopenia")'
            ),
            (
                '("plant protein" OR "soy protein" OR "pea protein" OR "legume protein")'
                ' AND ("muscle mass" OR "lean body mass" OR "muscle protein synthesis" OR "resistance training"'
                ' OR "athletic performance" OR "protein quality" OR "PDCAAS" OR "DIAAS")'
            ),
        ],
    },
    "cognition": {
        "name": "Cognitive Function & Neurological Health",
        "description": "Effects of plant-based diets on cognitive function, dementia risk, and neurological health outcomes.",
        "queries": [
            (
                '("plant-based diet" OR "vegan diet" OR "vegetarian diet" OR "whole food plant-based" OR "WFPB" OR "meat-free")'
                ' AND ("cognitive function" OR "cognition" OR "dementia" OR "Alzheimer" OR "cognitive decline"'
                ' OR "brain health" OR "neurological" OR "memory" OR "cognitive impairment")'
            ),
            (
                '("reduced meat" OR "meat reduction" OR "low animal fat" OR "dietary pattern")'
                ' AND ("cognitive function" OR "cognition" OR "dementia" OR "Alzheimer" OR "cognitive decline"'
                ' OR "brain health" OR "cognitive impairment")'
            ),
        ],
    },
    "longevity": {
        "name": "Longevity & All-Cause Mortality",
        "description": "Evidence on plant-based diets and their relationship with lifespan, all-cause mortality, and healthy aging.",
        "queries": [
            (
                '("plant-based diet" OR "vegan diet" OR "vegetarian diet" OR "whole food plant-based" OR "WFPB" OR "meat-free")'
                ' AND ("longevity" OR "all-cause mortality" OR "life expectancy" OR "healthy aging" OR "aging"'
                ' OR "mortality risk" OR "lifespan" OR "survival")'
            ),
            (
                '("reduced meat" OR "meat reduction" OR "animal product reduction" OR "dietary pattern")'
                ' AND ("longevity" OR "all-cause mortality" OR "life expectancy" OR "healthy aging"'
                ' OR "mortality risk" OR "lifespan")'
            ),
        ],
    },
    "nutrient_deficiencies": {
        "name": "Nutrient Deficiencies (B12, Iron, Omega-3, Zinc, Calcium)",
        "description": "Research on nutrient status, deficiency risk, and supplementation needs in those following plant-based diets.",
        "queries": [
            (
                '("plant-based diet" OR "vegan diet" OR "vegetarian diet" OR "whole food plant-based" OR "WFPB" OR "meat-free")'
                ' AND ("vitamin B12" OR "iron deficiency" OR "omega-3" OR "zinc deficiency" OR "calcium"'
                ' OR "nutrient deficiency" OR "micronutrient" OR "DHA" OR "EPA" OR "ferritin")'
            ),
            (
                '("vegan" OR "vegetarian" OR "plant-based")'
                ' AND ("supplementation" OR "B12 deficiency" OR "anemia" OR "iron status"'
                ' OR "omega-3 status" OR "zinc status" OR "calcium intake" OR "nutrient bioavailability")'
            ),
        ],
    },
}

# Study quality tiers: lower number = higher evidence quality
STUDY_QUALITY_TIERS = {
    "Meta-Analysis": 1,
    "Systematic Review": 1,
    "Randomized Controlled Trial": 2,
    "Clinical Trial, Phase III": 2,
    "Clinical Trial, Phase II": 2,
    "Controlled Clinical Trial": 2,
    "Observational Study": 3,
    "Cohort Studies": 3,
    "Longitudinal Studies": 3,
    "Prospective Studies": 3,
    "Cross-Sectional Studies": 4,
    "Case-Control Studies": 4,
    "Retrospective Studies": 4,
    "Case Reports": 5,
    "Editorial": 5,
    "Comment": 5,
    "Letter": 5,
    "Review": 3,  # Narrative review (not systematic)
}

# Minimum quality tier to include in narrative summaries (5 = excluded)
MIN_QUALITY_FOR_NARRATIVE = 4

# Years to fetch on first/bootstrap run
BOOTSTRAP_YEARS = 5

# Groq model for narrative summaries (70b: 100k TPD free tier)
GROQ_MODEL = "llama-3.3-70b-versatile"

# Groq model for stats extraction — smaller model, 500k TPD free tier,
# keeps stats extraction off the 70b quota entirely
GROQ_STATS_MODEL = "llama-3.1-8b-instant"

# Max studies to send per Groq summary call (prioritised by tier then recency).
# Groq free tier: 12,000 TPM hard limit. With 25 studies at 200-char abstracts:
# ~3,250 tokens (studies) + 500 (prompt) + 4,096 (max output) ≈ 7,850 — safely under.
MAX_STUDIES_PER_SUMMARY = 25

# Cap for stats + contested extraction (8b model, 6k TPM on free tier).
# 15 studies × ~150 tokens + 500 prompt + 2000 output ≈ 4,750 — safely under 6k.
MAX_STUDIES_PER_EXTRACTION = 15

# Seconds between PubMed API requests to respect rate limits
RATE_LIMIT_DELAY = 0.4
