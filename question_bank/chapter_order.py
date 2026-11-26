"""NCERT chapter sequence for the teacher's subject/class dropdown.

Sort at presentation time; never rename chapters or change stored IDs.
Unrecognised titles stay visible after the mapped textbook chapters.
"""
import re
import unicodedata

CHAPTERS = {
    ("mathematics", 11): ("Sets", "Relations and Functions", "Trigonometric Functions", "Complex Numbers and Quadratic Equations", "Linear Inequalities", "Permutations and Combinations", "Binomial Theorem", "Sequences and Series", "Straight Lines", "Conic Sections", "Introduction to Three Dimensional Geometry", "Limits and Derivatives", "Statistics", "Probability"),
    ("mathematics", 12): ("Relations and Functions", "Inverse Trigonometric Functions", "Matrices", "Determinants", "Continuity and Differentiability", "Application of Derivatives", "Integrals", "Application of Integrals", "Differential Equations", "Vector Algebra", "Three Dimensional Geometry", "Linear Programming", "Probability"),
    ("physics", 11): (
        "Units and Measurements", "Motion in a Straight Line", "Motion in a Plane",
        "Laws of Motion", "Work, Energy and Power",
        "System of Particles and Rotational Motion", "Gravitation",
        "Mechanical Properties of Solids", "Mechanical Properties of Fluids",
        "Thermal Properties of Matter", "Thermodynamics", "Kinetic Theory",
        "Oscillations", "Waves",
    ),
    ("physics", 12): (
        "Electric Charges and Fields", "Electrostatic Potential and Capacitance",
        "Current Electricity", "Moving Charges and Magnetism", "Magnetism and Matter",
        "Electromagnetic Induction", "Alternating Current", "Electromagnetic Waves",
        "Ray Optics and Optical Instruments", "Wave Optics",
        "Dual Nature of Radiation and Matter", "Atoms", "Nuclei",
        "Semiconductor Electronics: Materials, Devices and Simple Circuits",
    ),
    ("chemistry", 11): (
        "Some Basic Concepts of Chemistry", "Structure of Atom",
        "Classification of Elements and Periodicity in Properties",
        "Chemical Bonding and Molecular Structure", "Thermodynamics", "Equilibrium",
        "Redox Reactions", "Organic Chemistry: Some Basic Principles and Techniques",
        "Hydrocarbons",
    ),
    ("chemistry", 12): (
        "Solutions", "Electrochemistry", "Chemical Kinetics", "d- and f-Block Elements",
        "Coordination Compounds", "Haloalkanes and Haloarenes",
        "Alcohols, Phenols and Ethers", "Aldehydes, Ketones and Carboxylic Acids",
        "Amines", "Biomolecules",
    ),
    ("biology", 11): (
        "The Living World", "Biological Classification", "Plant Kingdom", "Animal Kingdom",
        "Morphology of Flowering Plants", "Anatomy of Flowering Plants",
        "Structural Organisation in Animals", "Cell: The Unit of Life", "Biomolecules",
        "Cell Cycle and Cell Division", "Photosynthesis in Higher Plants",
        "Respiration in Plants", "Plant Growth and Development",
        "Breathing and Exchange of Gases", "Body Fluids and Circulation",
        "Excretory Products and Their Elimination", "Locomotion and Movement",
        "Neural Control and Coordination", "Chemical Coordination and Integration",
    ),
    ("biology", 12): (
        "Sexual Reproduction in Flowering Plants", "Human Reproduction", "Reproductive Health",
        "Principles of Inheritance and Variation", "Molecular Basis of Inheritance",
        "Evolution", "Human Health and Disease", "Microbes in Human Welfare",
        "Biotechnology: Principles and Processes", "Biotechnology and Its Applications",
        "Organisms and Populations", "Ecosystem", "Biodiversity and Conservation",
    ),
}


def _key(name):
    name = unicodedata.normalize("NFKC", str(name)).casefold().replace("&", "and")
    name = re.sub(r"^\s*the\s+", "", name)
    return "".join(char for char in name if char.isalnum())


RANKS = {group: {_key(name): number for number, name in enumerate(names, 1)}
         for group, names in CHAPTERS.items()}

# Existing importer and starter-catalog spellings refer to the same positions.
ALIASES = {
    ("chemistry", 11): {
        "Chemical Thermodynamics": 5,
        "Classification of Elements and Periodicity": 3,
        "Organic Chemistry: Basic Principles and Techniques": 8,
        "Organic Chemistry – Some Basic Principles and Techniques": 8,
    },
    ("chemistry", 12): {"d and f Block Elements": 4, "d-block and f-block Elements": 4},
    ("physics", 11): {
        "Systems of Particles and Rotational Motion": 6,
        "System of Particles & Rotational Motion": 6,
    },
    ("physics", 12): {
        "Ray Optics": 9, "Semiconductor Electronics": 14,
        "Semiconductors": 14,
    },
    ("biology", 11): {"Structural Organization in Animals": 7},
    ("biology", 12): {"Biotechnology: Its Applications": 10},
}
for group, names in ALIASES.items():
    RANKS[group].update({_key(name): rank for name, rank in names.items()})


def chapter_sort_key(chapter):
    subject = str(chapter["subject"]).casefold()
    level = int(chapter["level"])
    rank = RANKS.get((subject, level), {}).get(_key(chapter["name"]), 10000)
    return (subject, level, rank, _key(chapter["name"]), chapter.get("id", 0))


def order_chapters(chapters):
    return sorted(chapters, key=chapter_sort_key)
