from django.core.management.base import BaseCommand
from django.db import transaction

from question_bank.models import Chapter, Subtopic

# Editable starter catalog, grouped by the class in which the chapter is taught.
CATALOG = {
    ("physics", 11): """
Units and Measurements|SI units;Dimensional analysis;Measurement errors
Motion in a Straight Line|Position and velocity;Acceleration;Motion graphs
Motion in a Plane|Vectors;Projectile motion;Circular motion
Laws of Motion|Newton's laws;Friction;Momentum
Work, Energy and Power|Work-energy theorem;Potential energy;Collisions
System of Particles and Rotational Motion|Centre of mass;Torque;Moment of inertia
Gravitation|Gravitational field;Escape velocity;Satellites
Mechanical Properties of Solids|Stress and strain;Elastic moduli
Mechanical Properties of Fluids|Fluid pressure;Bernoulli's principle;Viscosity
Thermal Properties of Matter|Expansion;Calorimetry;Heat transfer
Thermodynamics|First law;Thermodynamic processes;Second law
Kinetic Theory|Ideal gas;Degrees of freedom
Oscillations|Simple harmonic motion;Pendulums
Waves|Wave motion;Standing waves;Sound
""",
    ("physics", 12): """
Electric Charges and Fields|Coulomb's law;Electric field;Gauss's law
Electrostatic Potential and Capacitance|Electric potential;Capacitors;Dielectrics
Current Electricity|Resistance;Kirchhoff's laws;Wheatstone bridge
Moving Charges and Magnetism|Lorentz force;Biot–Savart law;Ampere's law
Magnetism and Matter|Magnetic dipoles;Magnetic materials
Electromagnetic Induction|Faraday's law;Lenz's law;Inductance
Alternating Current|AC circuits;Resonance;Transformers
Electromagnetic Waves|Wave properties;Electromagnetic spectrum
Ray Optics|Reflection;Refraction;Optical instruments
Wave Optics|Interference;Diffraction;Polarisation
Dual Nature of Radiation and Matter|Photoelectric effect;Matter waves
Atoms|Rutherford model;Bohr model;Spectra
Nuclei|Binding energy;Fission and fusion
Semiconductor Electronics|Semiconductors;Diodes;Logic gates
Experimental Skills|Measurements;Circuits;Optical experiments
""",
    ("chemistry", 11): """
Some Basic Concepts of Chemistry|Mole concept;Stoichiometry;Concentration
Structure of Atom|Atomic models;Quantum numbers;Electronic configuration
Classification of Elements and Periodicity|Periodic trends;Electronic configuration
Chemical Bonding and Molecular Structure|Lewis structures;Hybridisation;Molecular orbital theory
Chemical Thermodynamics|Enthalpy;Entropy;Gibbs energy
Equilibrium|Chemical equilibrium;Acids and bases;Solubility equilibria
Redox Reactions|Oxidation numbers;Balancing;Disproportionation
Organic Chemistry: Basic Principles and Techniques|Nomenclature;Isomerism;Electronic effects;Purification
Hydrocarbons|Alkanes;Alkenes and alkynes;Aromatic hydrocarbons
""",
    ("chemistry", 12): """
Solutions|Concentration;Raoult's law;Colligative properties
Electrochemistry|Electrochemical cells;Nernst equation;Conductance
Chemical Kinetics|Rate laws;Integrated rate equations;Arrhenius equation
p-Block Elements|Groups 13–14;Groups 15–16;Groups 17–18
d- and f-Block Elements|Transition elements;Lanthanoids and actinoids
Coordination Compounds|Nomenclature;Isomerism;Bonding
Haloalkanes and Haloarenes|Preparation;Substitution reactions
Alcohols, Phenols and Ethers|Alcohols;Phenols;Ethers
Aldehydes, Ketones and Carboxylic Acids|Carbonyl reactions;Carboxylic acids
Amines|Basicity;Preparation and reactions;Diazonium salts
Biomolecules|Carbohydrates;Proteins;Nucleic acids
Practical Chemistry|Qualitative analysis;Titrations;Organic functional groups
""",
    ("biology", 11): """
The Living World|Taxonomy;Nomenclature
Biological Classification|Monera and Protista;Fungi;Viruses and viroids
Plant Kingdom|Algae;Bryophytes and pteridophytes;Gymnosperms
Animal Kingdom|Non-chordates;Chordates
Morphology of Flowering Plants|Roots and stems;Leaves;Flowers and fruits
Anatomy of Flowering Plants|Plant tissues;Root, stem and leaf anatomy
Structural Organisation in Animals|Animal tissues;Frog
Cell: The Unit of Life|Cell membrane;Organelles;Nucleus
Biomolecules|Carbohydrates and lipids;Proteins;Enzymes
Cell Cycle and Cell Division|Cell cycle;Mitosis;Meiosis
Photosynthesis in Higher Plants|Light reactions;Calvin cycle;C4 pathway
Respiration in Plants|Glycolysis;Krebs cycle;Electron transport
Plant Growth and Development|Growth;Plant growth regulators
Breathing and Exchange of Gases|Breathing mechanics;Gas transport
Body Fluids and Circulation|Blood;Heart;Cardiac cycle
Excretory Products and Their Elimination|Nephron;Urine formation;Osmoregulation
Locomotion and Movement|Muscle contraction;Skeleton and joints
Neural Control and Coordination|Neurons;Nerve impulses;Nervous system
Chemical Coordination and Integration|Endocrine glands;Hormonal action
""",
    ("biology", 12): """
Sexual Reproduction in Flowering Plants|Gametophytes;Pollination;Double fertilisation
Human Reproduction|Reproductive systems;Gametogenesis;Menstrual cycle;Fertilisation and pregnancy
Reproductive Health|Contraception;Sexually transmitted infections;Assisted reproduction
Principles of Inheritance and Variation|Mendelian inheritance;Linkage;Genetic disorders
Molecular Basis of Inheritance|DNA replication;Transcription;Translation;Gene regulation
Evolution|Evidence;Natural selection;Hardy–Weinberg principle
Human Health and Disease|Infectious diseases;Immunity;Cancer
Microbes in Human Welfare|Industrial uses;Sewage treatment;Biocontrol
Biotechnology: Principles and Processes|Recombinant DNA;Vectors;PCR
Biotechnology and Its Applications|Agriculture;Medicine;Biosafety
Organisms and Populations|Adaptations;Population growth;Interactions
Ecosystem|Productivity;Decomposition;Energy flow
Biodiversity and Conservation|Biodiversity patterns;Conservation
""",
}


class Command(BaseCommand):
    help = "Create editable Class 11 and 12 chapters and starter subtopics."

    @transaction.atomic
    def handle(self, *args, **options):
        for (subject, level), chapters in CATALOG.items():
            for line in chapters.strip().splitlines():
                name, topics = line.split("|", 1)
                chapter, _ = Chapter.objects.get_or_create(subject=subject, level=level, name=name)
                for topic in topics.split(";"):
                    Subtopic.objects.get_or_create(chapter=chapter, name=topic)
        self.stdout.write(self.style.SUCCESS("NEET starter catalog is ready."))
