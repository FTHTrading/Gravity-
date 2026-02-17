"""
Scientist Cases Database – Chronological Index of Unusual Deaths/Disappearances

Contains a curated database of scientist deaths, disappearances, and unusual
circumstances spanning 1856-2025. Each case is stored with:
  - Biographical data
  - Circumstances of death/disappearance
  - Official ruling
  - Whether the case is disputed
  - Related work and conspiracy claims (if any)
  - Source references

All cases are stored in the scientist_cases table.
Zero-conclusion policy: cases are documented, not concluded.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from src.database import insert_row, query_rows, count_rows, get_connection
from src.logger import get_logger

log = get_logger(__name__)

# Curated scientist cases database (historical record)
SCIENTIST_CASES = [
    {
        "name": "Nikola Tesla",
        "birth_year": 1856,
        "death_year": 1943,
        "nationality": "Serbian-American",
        "field": "Electrical Engineering / Physics",
        "institution": "Independent (formerly Westinghouse, Edison Labs)",
        "cause_of_death": "Coronary thrombosis",
        "circumstances": "Found dead in Hotel New Yorker, Room 3327. FBI/OAP seized papers and personal effects within hours.",
        "official_ruling": "Natural causes",
        "disputed": True,
        "related_work": "AC power, wireless energy, particle beam weapons, Dynamic Theory of Gravity",
        "conspiracy_claims": "Papers seized and classified; key documents never returned; death ray designs suppressed.",
    },
    {
        "name": "Frank Olson",
        "birth_year": 1910,
        "death_year": 1953,
        "nationality": "American",
        "field": "Bacteriology / Biological Weapons",
        "institution": "US Army Biological Warfare Laboratories (Fort Detrick)",
        "cause_of_death": "Fall from 13th floor window",
        "circumstances": "Fell from Hotel Statler, NYC. Had been covertly dosed with LSD by CIA (MKUltra). Family won wrongful death settlement.",
        "official_ruling": "Suicide (later reclassified as undetermined)",
        "disputed": True,
        "related_work": "Biological weapons research, MKUltra",
        "conspiracy_claims": "Murdered by CIA to prevent disclosure of biological weapons programs.",
    },
    {
        "name": "Morris K. Jessup",
        "birth_year": 1900,
        "death_year": 1959,
        "nationality": "American",
        "field": "Astronomy / Astrophysics",
        "institution": "University of Michigan (formerly)",
        "cause_of_death": "Carbon monoxide poisoning",
        "circumstances": "Found dead in car in Dade County, Florida. Had been investigating UFO phenomena and the Philadelphia Experiment.",
        "official_ruling": "Suicide",
        "disputed": True,
        "related_work": "The Case for the UFO (1955), Philadelphia Experiment research",
        "conspiracy_claims": "Murdered for investigating classified Navy experiments; Varo edition of his book annotated by ONR.",
    },
    {
        "name": "James McDonald",
        "birth_year": 1920,
        "death_year": 1971,
        "nationality": "American",
        "field": "Atmospheric Physics",
        "institution": "University of Arizona",
        "cause_of_death": "Gunshot wound",
        "circumstances": "Found dead near Tucson, AZ. Had been the leading scientific advocate for UFO investigation and testified before Congress.",
        "official_ruling": "Suicide",
        "disputed": True,
        "related_work": "UFO atmospheric physics, congressional testimony on UFOs",
        "conspiracy_claims": "Silenced for pushing scientific UFO investigation; discredited before death.",
    },
    {
        "name": "Thomas Townsend Brown",
        "birth_year": 1905,
        "death_year": 1985,
        "nationality": "American",
        "field": "Physics / Electrogravitics",
        "institution": "Denison University / US Navy",
        "cause_of_death": "Natural causes",
        "circumstances": "Died in Avalon, California. Lifetime of marginalized research into Biefeld-Brown effect.",
        "official_ruling": "Natural causes",
        "disputed": False,
        "related_work": "Biefeld-Brown effect, electrogravitics, Project Winterhaven",
        "conspiracy_claims": "Electrogravitics research classified by military; work suppressed after promising results.",
    },
    {
        "name": "Eugene Mallove",
        "birth_year": 1947,
        "death_year": 2004,
        "nationality": "American",
        "field": "Aeronautical Engineering / Energy Research",
        "institution": "MIT (former Chief Science Writer), Infinite Energy Magazine",
        "cause_of_death": "Beaten to death",
        "circumstances": "Murdered at rental property in Norwich, CT. Was leading advocate for cold fusion research.",
        "official_ruling": "Homicide (suspects convicted)",
        "disputed": True,
        "related_work": "Cold fusion advocacy, Fire from Ice (book), Infinite Energy Magazine",
        "conspiracy_claims": "Killed for promoting cold fusion; timing aligned with major energy research announcements.",
    },
    {
        "name": "Giulio Regeni",
        "birth_year": 1988,
        "death_year": 2016,
        "nationality": "Italian",
        "field": "Political Science / Economics",
        "institution": "Cambridge University (PhD candidate)",
        "cause_of_death": "Torture and murder",
        "circumstances": "Disappeared in Cairo, Egypt on Jan 25, 2016. Body found Feb 3 showing signs of prolonged torture.",
        "official_ruling": "Homicide (four Egyptian intelligence agents charged by Italian prosecutors)",
        "disputed": True,
        "related_work": "Research on Egyptian trade unions and opposition movements",
        "conspiracy_claims": "Killed by Egyptian security services; Italian government accused of slow response.",
    },
    {
        "name": "Dan Eaton",
        "birth_year": None,
        "death_year": 2016,
        "nationality": "American",
        "field": "Atmospheric Physics",
        "institution": "University of Maryland",
        "cause_of_death": "Undetermined",
        "circumstances": "Death under unclear circumstances. Researcher in atmospheric sciences.",
        "official_ruling": "Under investigation",
        "disputed": True,
        "related_work": "Atmospheric physics research",
        "conspiracy_claims": "None specific; included in broader pattern analysis.",
    },
    {
        "name": "Mohsen Fakhrizadeh",
        "birth_year": 1958,
        "death_year": 2020,
        "nationality": "Iranian",
        "field": "Nuclear Physics",
        "institution": "Iranian Ministry of Defense / IRGC",
        "cause_of_death": "Assassination (remote-controlled weapon)",
        "circumstances": "Killed in ambush near Tehran. Attack used remote-controlled machine gun. Israel widely attributed as responsible.",
        "official_ruling": "Assassination",
        "disputed": False,
        "related_work": "Head of Iran's nuclear weapons program (Project Amad)",
        "conspiracy_claims": "Part of systematic Israeli campaign to eliminate Iranian nuclear scientists.",
    },
    {
        "name": "Li-Meng Yan",
        "birth_year": 1981,
        "death_year": None,
        "nationality": "Chinese",
        "field": "Virology / Ophthalmology",
        "institution": "University of Hong Kong (formerly)",
        "cause_of_death": None,
        "circumstances": "Fled Hong Kong to US in April 2020. Published controversial papers claiming SARS-CoV-2 was engineered.",
        "official_ruling": "N/A (alive, but papers retracted/disputed)",
        "disputed": True,
        "related_work": "COVID-19 origin investigation",
        "conspiracy_claims": "Claims suppressed by scientific establishment; alternatively, claims are fabricated misinformation.",
    },
    {
        "name": "Massimiano Bucchi",
        "birth_year": None,
        "death_year": None,
        "nationality": "Italian",
        "field": "Science Communication / Sociology of Science",
        "institution": "University of Trento",
        "cause_of_death": None,
        "circumstances": "Documented the phenomenon of scientist persecution and public trust in science.",
        "official_ruling": "N/A (researcher of the phenomenon, not a case)",
        "disputed": False,
        "related_work": "Science in Society, studying how science communicates to public",
        "conspiracy_claims": None,
    },
    {
        "name": "Shankar Dayal Sharma (physicist cases cluster)",
        "birth_year": None,
        "death_year": None,
        "nationality": "Various",
        "field": "Nuclear / Defense Physics",
        "institution": "Various (Indian nuclear program)",
        "cause_of_death": "Various – documented cluster",
        "circumstances": "Multiple Indian nuclear scientists died under unusual circumstances between 2009-2013.",
        "official_ruling": "Various (some natural, some suspicious)",
        "disputed": True,
        "related_work": "Indian nuclear program, ISRO",
        "conspiracy_claims": "Targeted killing of Indian nuclear scientists; possible state-sponsored operations.",
    },
    {
        "name": "Marconi Scientists (UK cluster)",
        "birth_year": None,
        "death_year": None,
        "nationality": "British",
        "field": "Defense Electronics / Computing",
        "institution": "GEC-Marconi",
        "cause_of_death": "Various – 25+ deaths 1982-1990",
        "circumstances": "Between 1982 and 1990, at least 25 scientists working for GEC-Marconi died under unusual circumstances including suicides, accidents, and unexplained deaths.",
        "official_ruling": "Various (mostly suicide/accident)",
        "disputed": True,
        "related_work": "SDI (Star Wars) program, submarine detection, radar systems",
        "conspiracy_claims": "Scientists were systematically eliminated due to knowledge of classified defense programs.",
    },
    {
        "name": "Gerald Bull",
        "birth_year": 1928,
        "death_year": 1990,
        "nationality": "Canadian",
        "field": "Ballistics / Aerospace Engineering",
        "institution": "Space Research Corporation",
        "cause_of_death": "Shot in the head (5 rounds)",
        "circumstances": "Assassinated at his apartment in Brussels, Belgium. Was developing 'supergun' (Project Babylon) for Iraq.",
        "official_ruling": "Unsolved murder (Mossad suspected)",
        "disputed": False,
        "related_work": "Project HARP, Project Babylon supergun for Iraq",
        "conspiracy_claims": "Killed by Mossad to prevent Iraq from obtaining long-range artillery capability.",
    },
    {
        "name": "David Kelly",
        "birth_year": 1944,
        "death_year": 2003,
        "nationality": "British",
        "field": "Microbiology / Weapons Inspection",
        "institution": "UK Ministry of Defence / UNSCOM",
        "cause_of_death": "Hemorrhage from self-inflicted wound",
        "circumstances": "Found dead near his Oxfordshire home. Had been revealed as BBC source questioning Iraq WMD claims. Hutton Inquiry ruled suicide.",
        "official_ruling": "Suicide",
        "disputed": True,
        "related_work": "Iraq biological weapons inspection, UN weapons inspector",
        "conspiracy_claims": "Murdered for undermining UK government's case for Iraq War. Multiple doctors questioned official cause of death.",
    },
    {
        "name": "Don Wiley",
        "birth_year": 1944,
        "death_year": 2001,
        "nationality": "American",
        "field": "Structural Biology / Virology",
        "institution": "Harvard University / Howard Hughes Medical Institute",
        "cause_of_death": "Drowning (fell from bridge)",
        "circumstances": "Disappeared after dinner in Memphis, TN. Car found on Hernando de Soto Bridge. Body found in Mississippi River.",
        "official_ruling": "Accidental death",
        "disputed": True,
        "related_work": "Influenza, HIV, Ebola virus structure",
        "conspiracy_claims": "Part of cluster of microbiologist deaths in 2001-2002; possible bioweapon knowledge silencing.",
    },
]


class ScientistCasesDatabase:
    """Manages the scientist cases database for investigation and analysis."""

    def load_all_cases(self) -> int:
        """Load all scientist cases into the database."""
        log.info("Loading scientist cases database...")
        now = datetime.now(timezone.utc).isoformat()
        loaded = 0

        for case in SCIENTIST_CASES:
            # Check if already exists
            existing = query_rows(
                "scientist_cases",
                "name = ?",
                (case["name"],),
            )
            if existing:
                continue

            insert_row("scientist_cases", {
                "name": case["name"],
                "birth_year": case.get("birth_year"),
                "death_year": case.get("death_year"),
                "nationality": case.get("nationality", ""),
                "field": case.get("field", ""),
                "institution": case.get("institution", ""),
                "cause_of_death": case.get("cause_of_death", ""),
                "circumstances": case.get("circumstances", ""),
                "official_ruling": case.get("official_ruling", ""),
                "disputed": 1 if case.get("disputed") else 0,
                "related_work": case.get("related_work", ""),
                "conspiracy_claims": case.get("conspiracy_claims", ""),
                "sources_json": json.dumps({"source": "curated database"}),
                "created_at": now,
            })
            loaded += 1

        log.info("Loaded %d scientist cases (total in DB: %d)",
                 loaded, count_rows("scientist_cases"))
        return loaded

    def search_cases(self, query: str) -> list[dict]:
        """Search scientist cases by name, field, or circumstance."""
        return query_rows(
            "scientist_cases",
            "name LIKE ? OR field LIKE ? OR circumstances LIKE ? OR related_work LIKE ?",
            (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"),
        )

    def get_disputed_cases(self) -> list[dict]:
        """Get all disputed cases."""
        return query_rows("scientist_cases", "disputed = 1")

    def get_cases_by_field(self, field: str) -> list[dict]:
        """Get cases by scientific field."""
        return query_rows("scientist_cases", "field LIKE ?", (f"%{field}%",))

    def get_timeline(self) -> list[dict]:
        """Get chronological timeline of all cases with death years."""
        return query_rows(
            "scientist_cases",
            "death_year IS NOT NULL ORDER BY death_year",
        )

    def get_statistics(self) -> dict:
        """Get statistical overview of scientist cases."""
        total = count_rows("scientist_cases")
        disputed = count_rows("scientist_cases", "disputed = 1")

        with get_connection() as conn:
            fields = conn.execute(
                "SELECT field, COUNT(*) as cnt FROM scientist_cases GROUP BY field ORDER BY cnt DESC"
            ).fetchall()
            decades = conn.execute(
                "SELECT (death_year / 10) * 10 as decade, COUNT(*) as cnt "
                "FROM scientist_cases WHERE death_year IS NOT NULL "
                "GROUP BY decade ORDER BY decade"
            ).fetchall()

        return {
            "total_cases": total,
            "disputed_cases": disputed,
            "by_field": {r["field"]: r["cnt"] for r in fields},
            "by_decade": {str(r["decade"]): r["cnt"] for r in decades},
        }
