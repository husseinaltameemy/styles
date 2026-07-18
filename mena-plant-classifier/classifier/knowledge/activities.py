"""Therapeutic-activity lexicon.

Maps a canonical pharmacological activity label to the surface forms actually
used in medicinal-plant abstracts and keyword lists. Matching is done with
word-boundary regular expressions (see ``classifier.activities``) so that, e.g.,
``anti`` and ``antidiabetic`` do not both fire on the same word.

Design notes for accuracy:

* Hyphen / space / concatenation variants are all covered
  (``anti-cancer`` / ``anti cancer`` / ``anticancer``) via a normalisation step
  in the matcher, so each pattern here is listed once in its plainest form.
* ``anticancer`` and ``antitumor`` are grouped under one canonical label
  (``Anticancer/Antitumor``) because papers use them interchangeably, but the
  matched surface term is retained as *evidence* so the distinction is not lost.
* British/American spellings (tumour/tumor, oedema/edema, anaemia/anemia,
  haemo/hemo) are both included.
"""
from __future__ import annotations

# canonical label -> list of surface synonyms (lower-case, hyphen/space agnostic)
ACTIVITIES: dict[str, list[str]] = {
    "Anticancer/Antitumor": [
        "anticancer", "anti cancer", "anticarcinogenic", "anticarcinoma",
        "antitumor", "antitumour", "anti tumor", "anti tumour", "antineoplastic",
        "antiproliferative", "anti proliferative", "cytotoxic", "cytotoxicity",
        "chemopreventive", "chemoprevention", "chemotherapeutic", "apoptotic",
        "apoptosis induction", "pro apoptotic", "antimetastatic", "anti metastatic",
        "antiangiogenic", "anti angiogenic", "antileukemic", "anti leukemic",
        "antimelanoma", "tumor growth inhibition", "anti breast cancer",
        "anti colon cancer", "anti lung cancer", "anti hepatocellular",
        "anti carcinogenic", "genotoxic protection",
    ],
    "Antidiabetic": [
        "antidiabetic", "anti diabetic", "antihyperglycemic", "antihyperglycaemic",
        "anti hyperglycemic", "hypoglycemic", "hypoglycaemic", "hypoglycaemia",
        "glucose lowering", "blood glucose", "insulin sensitizing",
        "insulin resistance", "alpha glucosidase inhibitory", "alpha amylase inhibitory",
        "antidiabetes", "diabetes mellitus", "streptozotocin", "glycemic control",
    ],
    "Anti-inflammatory": [
        "anti inflammatory", "antiinflammatory", "anti-inflammation",
        "antiinflammation", "anti inflammation", "cox 2 inhibition",
        "nf kappa b", "cytokine suppression", "carrageenan induced edema",
        "carrageenan induced oedema", "antiedematous",
    ],
    "Antioxidant": [
        "antioxidant", "anti oxidant", "radical scavenging", "free radical scavenging",
        "dpph", "abts", "frap", "reducing power", "lipid peroxidation inhibition",
        "oxidative stress", "reactive oxygen species scavenging", "ros scavenging",
    ],
    "Antimicrobial": [
        "antimicrobial", "anti microbial", "antibacterial", "anti bacterial",
        "bactericidal", "antibiotic activity", "growth inhibition of bacteria",
        "against staphylococcus", "against escherichia", "against pseudomonas",
        "minimum inhibitory concentration", "antibiofilm", "anti biofilm",
    ],
    "Antifungal": [
        "antifungal", "anti fungal", "fungicidal", "anticandidal", "anti candidal",
        "against candida", "against aspergillus", "antimycotic",
    ],
    "Antiviral": [
        "antiviral", "anti viral", "virucidal", "against herpes", "anti hiv",
        "anti influenza", "anti sars", "antihepatitis", "anti hepatitis virus",
        "anti coronavirus", "antiretroviral",
    ],
    "Antiparasitic": [
        "antiparasitic", "anti parasitic", "antimalarial", "anti malarial",
        "antiplasmodial", "anti plasmodial", "antileishmanial", "anti leishmanial",
        "antitrypanosomal", "anti trypanosomal", "anthelmintic", "antischistosomal",
        "antigiardial", "antiprotozoal", "larvicidal against anopheles",
    ],
    "Hepatoprotective": [
        "hepatoprotective", "hepato protective", "liver protective",
        "anti hepatotoxic", "antihepatotoxic", "against liver damage",
        "carbon tetrachloride induced", "ccl4 induced",
    ],
    "Nephroprotective": [
        "nephroprotective", "nephro protective", "renoprotective",
        "kidney protective", "against nephrotoxicity", "anti nephrotoxic",
    ],
    "Cardioprotective": [
        "cardioprotective", "cardio protective", "against myocardial",
        "anti ischemic", "anti ischaemic", "against cardiotoxicity",
    ],
    "Antihypertensive": [
        "antihypertensive", "anti hypertensive", "blood pressure lowering",
        "hypotensive", "ace inhibitory", "angiotensin converting enzyme inhibitory",
        "vasorelaxant", "vasodilator", "vasodilatory",
    ],
    "Antihyperlipidemic": [
        "antihyperlipidemic", "anti hyperlipidemic", "hypolipidemic", "hypolipidaemic",
        "hypocholesterolemic", "cholesterol lowering", "antihyperlipidaemic",
        "lipid lowering", "antiatherogenic", "anti atherosclerotic",
    ],
    "Neuroprotective": [
        "neuroprotective", "neuro protective", "anti alzheimer", "antialzheimer",
        "anti parkinson", "acetylcholinesterase inhibitory", "cholinesterase inhibitory",
        "memory enhancing", "nootropic", "anti amnesic", "antidementia",
    ],
    "Analgesic": [
        "analgesic", "antinociceptive", "anti nociceptive", "pain relieving",
        "antihyperalgesic",
    ],
    "Antipyretic": [
        "antipyretic", "anti pyretic", "fever reducing", "febrifuge",
    ],
    "Wound healing": [
        "wound healing", "wound-healing", "cicatrizant", "re epithelialization",
        "burn healing", "tissue regeneration", "pro healing",
    ],
    "Gastroprotective/Antiulcer": [
        "gastroprotective", "gastro protective", "antiulcer", "anti ulcer",
        "antiulcerogenic", "anti gastric ulcer", "against gastric lesions",
    ],
    "Antidiarrheal": [
        "antidiarrheal", "antidiarrhoeal", "anti diarrheal", "anti diarrhoeal",
    ],
    "Antiobesity": [
        "antiobesity", "anti obesity", "anti adipogenic", "antiadipogenic",
        "weight reducing", "lipase inhibitory", "pancreatic lipase inhibition",
    ],
    "Immunomodulatory": [
        "immunomodulatory", "immuno modulatory", "immunostimulant", "immunostimulatory",
        "immunosuppressive", "immune enhancing", "adjuvant activity",
    ],
    "Antidepressant/Anxiolytic": [
        "antidepressant", "anti depressant", "anxiolytic", "anti anxiety",
        "antistress", "sedative", "against depression",
    ],
    "Antiasthmatic/Bronchodilator": [
        "antiasthmatic", "anti asthmatic", "bronchodilator", "bronchodilatory",
        "anti asthma", "relaxant of tracheal",
    ],
    "Antispasmodic": [
        "antispasmodic", "anti spasmodic", "spasmolytic", "smooth muscle relaxant",
        "anti spasm",
    ],
    "Antifertility/Reproductive": [
        "antifertility", "anti fertility", "contraceptive", "aphrodisiac",
        "spermatogenic", "antispermatogenic", "estrogenic", "oestrogenic",
        "uterotonic",
    ],
    "Anti-arthritic": [
        "antiarthritic", "anti arthritic", "antirheumatic", "anti rheumatic",
        "against rheumatoid", "antigout", "anti gout",
    ],
    "Antithrombotic": [
        "antithrombotic", "anti thrombotic", "anticoagulant", "anti coagulant",
        "antiplatelet", "anti platelet", "fibrinolytic",
    ],
    "Larvicidal/Insecticidal": [
        "larvicidal", "insecticidal", "mosquitocidal", "repellent activity",
        "against culex", "against aedes", "acaricidal",
    ],
    "Antidote/Detoxifying": [
        "antivenom", "anti venom", "antisnake", "detoxifying", "antidotal",
    ],
    "Diuretic": [
        "diuretic", "antidiuretic", "natriuretic",
    ],
    "Laxative": [
        "laxative", "purgative", "cathartic",
    ],
    "Antilithic": [
        "antilithic", "antiurolithiatic", "anti urolithiatic", "antilithiasis",
        "kidney stone", "nephrolithiasis",
    ],
    "Dermatological/Anti-acne": [
        "anti acne", "antiacne", "antipsoriatic", "anti psoriatic",
        "depigmenting", "tyrosinase inhibitory", "skin whitening", "antimelanogenic",
    ],
    "Galactagogue": [
        "galactagogue", "galactogogue", "milk production",
    ],
    "Vasodilator": [
        "vasodilator", "vasodilatory", "vasorelaxant",
    ],
    "Uterotonic": [
        "uterotonic", "oxytocic",
    ],
    "Estrogenic": [
        "estrogenic", "oestrogenic", "phytoestrogen",
    ],
    "Antiemetic": [
        "antiemetic", "anti emetic", "anti nausea",
    ],
}
