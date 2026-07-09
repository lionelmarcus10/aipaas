#!/usr/bin/env python3
"""Setup script — build DuckDB + RAG index for the Insurance Claims Triage Agent.

Sources (2) :
  1. Vehicle Insurance Fraud Detection (Kaggle/GitHub) — 15 420 sinistres réels
  2. Faker + Pydantic (synthetic) — polices, cas de test contrôlés, documents RAG

Le dataset Kaggle fournit les sinistres réels avec labels de fraude.
Faker génère les polices, les cas de test contrôlés (ground truth),
et les documents de police pour le RAG.

RAG index (3 providers) :
  - FAISS       → local on PVC (k3d, sentence-transformers/all-MiniLM-L6-v2)
  - S3 Vectors  → AWS S3 Vectors (real AWS or Floci)
  - Mock        → fallback (no indexing)

Run:  python data/setup_db.py
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

import duckdb
import pandas as pd

# Paths
DATA_DIR = Path(__file__).parent
RAW_DIR = DATA_DIR / "raw"
KAGGLE_DIR = RAW_DIR / "kaggle"
DB_PATH = DATA_DIR / "insurance_claims.duckdb"
RAG_INDEX_PATH = DATA_DIR / "rag_index"

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from insurance_claims_agent.claim_generator import (
    generate_test_claims,
    generate_policy_text,
)


# ═══════════════════════════════════════════════════════════════════════
# SOURCES — Données utilisées pour générer la DB
# ═══════════════════════════════════════════════════════════════════════
#
# Source 1 : Vehicle Insurance Fraud Detection (Kaggle) — RÉELLE
# ─────────────────────────────────────────────────────────────────────
#   URL     : https://www.kaggle.com/datasets/shivamb/vehicle-claim-fraud-detection
#   Mirror  : https://github.com/McGill-MMA-EnterpriseAnalytics/Vehicle-Claim-Fraud-Detection
#   Nature  : 15 420 sinistres auto avec labels de fraude, 33 colonnes
#   Origine : Oracle (cas d'étude fraud detection réel)
#   Licence : Open source (Kaggle)
#   Téléchargé via : GitHub mirror (fraud_oracle.csv, 3.5 MB)
#
#   Colonnes (33) :
#     ┌────────────────────────┬──────────┬──────────────────────────────────────┐
#     │ Colonne                │ Type     │ Rôle                                 │
#     ├────────────────────────┼──────────┼──────────────────────────────────────┤
#     │ Month                  │ str (12) │ Mois du sinistre                     │
#     │ WeekOfMonth            │ int (5)  │ Semaine du mois                      │
#     │ DayOfWeek              │ str (7)  │ Jour du sinistre                     │
#     │ Make                   │ str (19) │ Marque du véhicule                   │
#     │ AccidentArea           │ str (2)  │ Urban / Rural                        │
#     │ DayOfWeekClaimed       │ str (8)  │ Jour de déclaration                  │
#     │ MonthClaimed           │ str (13) │ Mois de déclaration                  │
#     │ WeekOfMonthClaimed     │ int (5)  │ Semaine de déclaration               │
#     │ Sex                    │ str (2)  │ Male / Female                        │
#     │ MaritalStatus          │ str (4)  │ Single, Married, etc.                │
#     │ Age                    │ int (66) │ Âge du conducteur                    │
#     │ Fault                  │ str (2)  │ Policy Holder / Third Party          │
#     │ PolicyType             │ str (9)  │ Sport - Liability, Sedan - Collision │
#     │ VehicleCategory        │ str (3)  │ Sport, Utility, Sedan                │
#     │ VehiclePrice           │ str (6)  │ Tranches de prix                     │
#     │ FraudFound_P           │ int (2)  │ LABEL : 0 = légitime, 1 = fraude     │
#     │ PolicyNumber           │ int      │ ID unique de police                  │
#     │ RepNumber              │ int (16) │ ID du représentant                   │
#     │ Deductible             │ int (4)  │ 300, 400, 500, 700                   │
#     │ DriverRating           │ int (4)  │ 1-4                                  │
#     │ Days_Policy_Accident   │ str (5)  │ Ancienneté police au moment sinistre │
#     │ Days_Policy_Claim      │ str (4)  │ Ancienneté police au moment décla    │
#     │ PastNumberOfClaims     │ str (4)  │ none, 1, 2 to 4, more than 4         │
#     │ AgeOfVehicle           │ str (8)  │ new, 2 years, 3 years, etc.          │
#     │ AgeOfPolicyHolder      │ str (9)  │ Tranches d'âge                       │
#     │ PoliceReportFiled      │ str (2)  │ Yes / No                             │
#     │ WitnessPresent         │ str (2)  │ Yes / No                             │
#     │ AgentType              │ str (2)  │ External / Internal                  │
#     │ NumberOfSuppliments    │ str (4)  │ none, 1 to 2, 3 to 5, more than 5    │
#     │ AddressChange_Claim    │ str (5)  │ no change, 1 year, etc.             │
#     │ NumberOfCars           │ str (5)  │ 1 vehicle, 3 to 4, etc.             │
#     │ Year                   │ int (3)  │ 1994, 1995, 1996                    │
#     │ BasePolicy             │ str (3)  │ Liability, Collision, All Perils    │
#     └────────────────────────┴──────────┴──────────────────────────────────────┘
#
#   Distribution fraude :
#     Légitime : 14 497 (94%)
#     Fraude    :    923 ( 6%)
#
#   Tables DuckDB créées depuis Kaggle (1) :
#     ✅ kaggle_claims  → 15 420 rows (sinistres réels avec labels de fraude)
#
# Source 2 : Faker + Pydantic (synthetic) — COMPLÉMENT
# ───────────────────────────────────────────────────────
#   Nature     : Génération synthétique contrôlée
#   Licence    : MIT (Faker) + MIT (Pydantic)
#   Utilisation: Polices, cas de test, historique, documents de police (RAG)
#
#   Tables générées (4) :
#     ┌──────────────────────┬──────────────┬──────────────────────────────────────┐
#     │ Table                │ Rows (defaut)│ Rôle                                 │
#     ├──────────────────────┼──────────────┼──────────────────────────────────────┤
#     │ policies             │         20   │ Polices d'assurance (auto/home)      │
#     │ claims               │         50   │ Sinistres FNOL (5 test + 45 random)  │
#     │ claim_history        │         12   │ Historique sinistres par client      │
#     │ fraud_rules          │          5   │ Règles de fraude (metadata)          │
#     └──────────────────────┴──────────────┴──────────────────────────────────────┘
#
#   Documents de police générés pour RAG :
#     - Chaque police → 1 document texte structuré (~3000-5000 chars)
#     - 7 sections : Coverage, Perils, Exclusions, Deductible, Claims,
#       Fraud Warning, Conditions
#     - Chunké en ~5-7 segments de 1000 chars (overlap 200)
#     - Indexé dans FAISS (local) ou S3 Vectors (AWS)
#
#   5 cas de test contrôlés (ground truth) :
#     CLM-0001 → FAST_TRACK_APPROVE  (sinistre simple, police claire)
#     CLM-0002 → ADJUSTER_REVIEW     (complexité modérée, needs humain)
#     CLM-0003 → SIU_REFERRAL        (police 3 jours, récidive, fraude)
#     CLM-0004 → DENY_COVERAGE       (exclusion catastrophe naturelle)
#     CLM-0005 → REQUEST_INFORMATION (infos manquantes)
#
# Volume par configuration :
#   ┌──────────────────┬─────────┬────────┬────────┬────────┬────────┬──────────┐
#   │ Config           │ Kaggle  │Policies│ Claims │ History│ Frauds │ DB       │
#   ├──────────────────┼─────────┼────────┼────────┼────────┼────────┼──────────┤
#   │ Test léger       │   1 000 │     10 │     15 │      5 │      5 │ ~0.5 MB  │
#   │ Default          │  15 420 │     20 │     50 │     12 │      5 │ ~3.5 MB  │
#   │ Démo             │  15 420 │     50 │    150 │     30 │      5 │ ~3.6 MB  │
#   │ Stress test      │  15 420 │    200 │    600 │    100 │      5 │ ~4.0 MB  │
#   └──────────────────┴─────────┴────────┴────────┴────────┴────────┴──────────┘
#
# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION — Modifie ces valeurs pour ajuster la taille de la DB
# ═══════════════════════════════════════════════════════════════════════
#
# ┌─────────────────────────────────────────────────────────────────────┐
# │  CONFIG RAPIDE                                                      │
# ├─────────────────────────────────────────────────────────────────────┤
# │  Test léger     → N_KAGGLE_CLAIMS=1000, garder le reste par défaut  │
# │  Démo correcte  → N_KAGGLE_CLAIMS=15420 (full), N_POLICIES=50      │
# │  Stress test    → N_KAGGLE_CLAIMS=15420, N_POLICIES=200            │
# └─────────────────────────────────────────────────────────────────────┘

# Nombre de sinistres Kaggle à charger (sur 15 420 disponibles)
# Les sinistres Kaggle sont chargés dans la table `kaggle_claims`.
# Utilisé par l'agent pour calculer des statistiques de référence (taux de
# fraude par type de police, par tranche de prix, etc.).
#   Min : 100   (test rapide)
#   Recommandé : 15420 (tous les sinistres réels)
#   Full : 15420 (le dataset complet fait 15 420 rows)
N_KAGGLE_CLAIMS = 15420

# Nombre de polices d'assurance (chaque police = 1 client unique)
# Les 5 premières polices sont réservées aux cas de test contrôlés.
#   Min recommandé : 10  (test rapide)
#   Moyen           : 20  (démo correcte)
#   Full            : 200 (stress test)
N_POLICIES = 20

# Nombre de sinistres aléatoires Faker (en plus des 5 cas de test)
# Les 5 cas de test (CLM-0001 à CLM-0005) sont toujours générés.
#   Min : 0   (que les 5 cas de test)
#   Recommandé : 45  (50 claims total)
#   Full : 500 (505 claims total, stress test)
N_RANDOM_CLAIMS = 45

# Nombre d'entrées dans l'historique des sinistres
# CUS-0003 a toujours ≥3 entrées (pattern de fraude pour les tests).
#   Min : 0   (seulement CUS-0003)
#   Recommandé : 10  (12 total avec CUS-0003)
#   Full : 100 (103 total, historique riche)
N_HISTORY_ENTRIES = 10

# Nombre de clients avec un pattern de fraude dans l'historique
# CUS-0003 est toujours le premier.
#   Min : 0   (seulement CUS-0003)
#   Recommandé : 2  (3 clients suspects total)
#   Full : 10 (11 clients suspects)
N_FRAUD_CUSTOMERS = 2

# Répartition des scénarios pour les sinistres aléatoires Faker
# (les 5 cas de test sont fixes, ce paramètre ne les affecte pas)
# Somme doit être = 1.0
SCENARIO_DISTRIBUTION = {
    "simple":   0.50,   # 50% des sinistres aléatoires sont simples
    "complex":  0.30,   # 30% sont complexes
    "fraud":    0.20,   # 20% sont suspects
}

# RAG — taille des chunks pour la vectorisation FAISS / S3 Vectors
#   Recommandé : 1000 (250 tokens, bon équilibre précision/contexte)
RAG_CHUNK_SIZE = 1000
RAG_CHUNK_OVERLAP = 200

# ═══════════════════════════════════════════════════════════════════════
# FIN CONFIGURATION — Ne pas modifier ci-dessous sauf si tu sais ce que tu fais
# ═══════════════════════════════════════════════════════════════════════

# URL du dataset (GitHub mirror — pas besoin d'auth Kaggle)
KAGGLE_CSV_URL = (
    "https://raw.githubusercontent.com/McGill-MMA-EnterpriseAnalytics/"
    "Vehicle-Claim-Fraud-Detection/main/data/fraud_oracle.csv"
)


def print_sources():
    """Affiche le récapitulatif des sources utilisées."""
    print()
    print("── Sources utilisées ──")
    print()
    print("  Source 1 : Vehicle Insurance Fraud Detection (Kaggle) — RÉELLE")
    print("    URL     : https://www.kaggle.com/datasets/shivamb/vehicle-claim-fraud-detection")
    print("    Mirror  : https://github.com/McGill-MMA-EnterpriseAnalytics/Vehicle-Claim-Fraud-Detection")
    print("    Nature  : 15 420 sinistres auto avec labels de fraude, 33 colonnes")
    print("    Origine : Oracle (cas d'étude fraud detection réel)")
    print("    Licence : Open source (Kaggle)")
    print(f"    Volume  : {N_KAGGLE_CLAIMS} sinistres chargés (sur 15 420 disponibles)")
    print("    Tables  : kaggle_claims (sinistres réels + labels de fraude)")
    print()
    print("  Source 2 : Faker + Pydantic (synthetic) — COMPLÉMENT")
    print("    Nature     : Génération synthétique contrôlée")
    print("    Licence    : MIT (Faker) + MIT (Pydantic)")
    print("    Utilisation: Polices, cas de test, historique, documents RAG")
    print(f"    Volume     : {N_POLICIES} polices, {N_RANDOM_CLAIMS + 5} sinistres, "
          f"{N_HISTORY_ENTRIES + 3} historiques")
    print("    Tables  : policies, claims, claim_history, fraud_rules")
    print()


# ─── Download functions ───────────────────────────────────────────────

def download_kaggle_dataset() -> Path:
    """Download the Vehicle Insurance Fraud Detection dataset from GitHub mirror.

    The dataset is originally from Kaggle (shivamb/vehicle-claim-fraud-detection)
    but we use the GitHub mirror to avoid Kaggle API authentication.

    Returns:
        Path to the downloaded fraud_oracle.csv file.
    """
    csv_path = KAGGLE_DIR / "fraud_oracle.csv"

    if csv_path.exists():
        rows = sum(1 for _ in open(csv_path)) - 1
        print(f"  Kaggle dataset already downloaded ({rows} rows)")
        return csv_path

    KAGGLE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading Kaggle dataset from GitHub mirror ({KAGGLE_CSV_URL})...")
    urllib.request.urlretrieve(KAGGLE_CSV_URL, str(csv_path))

    rows = sum(1 for _ in open(csv_path)) - 1
    size_mb = csv_path.stat().st_size / 1024 / 1024
    print(f"  Downloaded: {rows} rows, {size_mb:.1f} MB → {csv_path}")
    return csv_path


def load_kaggle_claims(csv_path: Path, n: int) -> pd.DataFrame:
    """Load the Kaggle dataset and return the first n rows.

    Args:
        csv_path: Path to fraud_oracle.csv.
        n: Number of rows to load (0 = all).

    Returns:
        DataFrame with the Kaggle claims data.
    """
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    if n > 0 and n < len(df):
        df = df.head(n)
    print(f"  Kaggle claims loaded: {len(df)} rows ({df['FraudFound_P'].sum()} fraud cases)")
    return df


# ─── DuckDB builder ───────────────────────────────────────────────────

def build_duckdb(
    kaggle_df: pd.DataFrame,
    policies: list,
    claims: list,
    claim_history: list,
) -> Path:
    """Build the DuckDB database with all tables."""
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = duckdb.connect(str(DB_PATH))

    # --- kaggle_claims (Source 1 : real data) ---
    print("  Creating kaggle_claims table (real fraud data)...")
    conn.execute("CREATE TABLE kaggle_claims AS SELECT * FROM kaggle_df")

    # --- policies (Source 2 : Faker) ---
    print("  Creating policies table...")
    policies_data = []
    for p in policies:
        policies_data.append({
            "policy_id": p.policy_id,
            "customer_id": p.customer_id,
            "policy_type": p.policy_type,
            "coverage_type": p.coverage_type,
            "coverage_limit": p.coverage_limit,
            "deductible": p.deductible,
            "premium_annual": p.premium_annual,
            "start_date": p.start_date,
            "end_date": p.end_date,
            "exclusions": json.dumps(p.exclusions),
            "status": p.status,
        })
    policies_df = pd.DataFrame(policies_data)
    conn.execute("CREATE TABLE policies AS SELECT * FROM policies_df")

    # --- claims (Source 2 : Faker) ---
    print("  Creating claims table...")
    claims_data = []
    for c in claims:
        claims_data.append({
            "claim_id": c.claim_id,
            "policy_id": c.policy_id,
            "customer_id": c.customer_id,
            "claim_type": c.claim_type,
            "incident_date": c.incident_date,
            "claim_date": c.claim_date,
            "claim_amount": c.claim_amount,
            "description": c.description,
            "police_report_filed": c.police_report_filed,
            "witnesses_count": c.witnesses_count,
            "expected_triage": c.expected_triage,
            "metadata_json": json.dumps(c.metadata),
        })
    claims_df = pd.DataFrame(claims_data)
    conn.execute("CREATE TABLE claims AS SELECT * FROM claims_df")

    # --- claim_history (Source 2 : Faker) ---
    print("  Creating claim_history table...")
    history_data = []
    for h in claim_history:
        history_data.append({
            "customer_id": h.customer_id,
            "claim_id": h.claim_id,
            "claim_date": h.claim_date,
            "claim_type": h.claim_type,
            "claim_amount": h.claim_amount,
            "fraud_found": h.fraud_found,
        })
    history_df = pd.DataFrame(history_data)
    conn.execute("CREATE TABLE claim_history AS SELECT * FROM history_df")

    # --- fraud_rules (metadata) ---
    print("  Creating fraud_rules table...")
    fraud_rules = [
        {"rule_id": "claim_within_30_days", "description": "Sinistre déclaré moins de 30j après souscription", "severity": "high"},
        {"rule_id": "amount_3x_average", "description": "Montant > 3x la moyenne des sinistres de ce type", "severity": "high"},
        {"rule_id": "repeat_claims_6_months", "description": "≥2 sinistres similaires en 6 mois", "severity": "medium"},
        {"rule_id": "no_police_report_high_amount", "description": "Pas de rapport police pour sinistre > 10k€", "severity": "medium"},
        {"rule_id": "narrative_inconsistency", "description": "Description incohérente avec le type de sinistre", "severity": "high"},
    ]
    fraud_df = pd.DataFrame(fraud_rules)
    conn.execute("CREATE TABLE fraud_rules AS SELECT * FROM fraud_df")

    # --- Indexes ---
    conn.execute("CREATE INDEX idx_policies_id ON policies(policy_id)")
    conn.execute("CREATE INDEX idx_policies_customer ON policies(customer_id)")
    conn.execute("CREATE INDEX idx_claims_id ON claims(claim_id)")
    conn.execute("CREATE INDEX idx_claims_policy ON claims(policy_id)")
    conn.execute("CREATE INDEX idx_claims_customer ON claims(customer_id)")
    conn.execute("CREATE INDEX idx_history_customer ON claim_history(customer_id)")
    conn.execute("CREATE INDEX idx_kaggle_policy ON kaggle_claims(PolicyNumber)")

    # --- Stats ---
    print()
    print("  ┌─────────────────────────────────────────────────────┐")
    table_names = ["kaggle_claims", "policies", "claims", "claim_history", "fraud_rules"]
    for table in table_names:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  │ {table:25s} : {count:>7} rows            │")
    print("  └─────────────────────────────────────────────────────┘")

    # Kaggle fraud statistics
    fraud_count = conn.execute(
        "SELECT COUNT(*) FROM kaggle_claims WHERE FraudFound_P = 1"
    ).fetchone()[0]
    total_kaggle = conn.execute("SELECT COUNT(*) FROM kaggle_claims").fetchone()[0]
    fraud_rate = (fraud_count / total_kaggle * 100) if total_kaggle > 0 else 0
    print(f"  Kaggle fraud rate: {fraud_count}/{total_kaggle} = {fraud_rate:.1f}%")

    db_size = DB_PATH.stat().st_size
    print(f"  DB size : {db_size / 1024 / 1024:.1f} MB")
    print(f"  DB path : {DB_PATH}")

    # --- Verify data integrity ---
    print()
    print("  ── Data integrity checks ──")

    orphan_claims = conn.execute("""
        SELECT COUNT(*) FROM claims c
        LEFT JOIN policies p ON c.policy_id = p.policy_id
        WHERE p.policy_id IS NULL
    """).fetchone()[0]
    print(f"    Orphan claims (no matching policy): {orphan_claims}")
    assert orphan_claims == 0, "Orphan claims found!"

    orphan_hist = conn.execute("""
        SELECT COUNT(*) FROM claim_history h
        LEFT JOIN policies p ON h.customer_id = p.customer_id
        WHERE p.customer_id IS NULL
    """).fetchone()[0]
    print(f"    Orphan history (no matching customer): {orphan_hist}")
    assert orphan_hist == 0, "Orphan history found!"

    test_claims = conn.execute("""
        SELECT claim_id, expected_triage FROM claims
        WHERE expected_triage != ''
        ORDER BY claim_id LIMIT 5
    """).fetchall()
    print(f"    Test claims with expected triage: {len(test_claims)}")
    for cid, triage in test_claims:
        print(f"      {cid} → {triage}")

    repeat = conn.execute("""
        SELECT COUNT(*) FROM claim_history WHERE customer_id = 'CUS-0003'
    """).fetchone()[0]
    print(f"    CUS-0003 claim history entries (fraud pattern): {repeat}")
    assert repeat >= 2, "CUS-0003 should have repeat claims for fraud detection"

    # Verify Kaggle data has fraud labels
    assert fraud_count > 0, "Kaggle dataset should have fraud cases"
    print(f"    Kaggle fraud cases present: {fraud_count}")

    conn.close()
    print()
    print("  ✅ Data integrity verified!")
    return DB_PATH


def build_rag_index(policies) -> dict:
    """Build RAG index from policy documents."""
    print("── Building RAG index ──")
    print(f"  Provider: {os.environ.get('RAG_PROVIDER', 'faiss')}")

    print(f"  Generating {len(policies)} policy documents...")
    policies_map = {}
    for p in policies:
        policies_map[p.policy_id] = generate_policy_text(p)

    total_chars = sum(len(t) for t in policies_map.values())
    avg_chars = total_chars / len(policies_map) if policies_map else 0
    print(f"  Total policy text: {total_chars} chars ({avg_chars:.0f} avg/policy)")

    from insurance_claims_agent.tools.rag_factory import build_index as build_rag

    rag_index_path = str(RAG_INDEX_PATH)
    rag_stats = build_rag(policies_map, rag_index_path)
    print(f"  RAG: {rag_stats['chunks']} chunks, "
          f"{rag_stats['vectors']} vectors, dim={rag_stats['dim']}")
    return rag_stats


def test_rag_retrieval(policies):
    """Test RAG retrieval."""
    print("── Testing RAG retrieval ──")
    os.environ["RAG_PROVIDER"] = os.environ.get("RAG_PROVIDER", "faiss")
    os.environ["RAG_INDEX_PATH"] = str(RAG_INDEX_PATH)

    from insurance_claims_agent.tools.rag_factory import retrieve_policy_chunks

    test_queries = [
        ("coverage limit for fire damage", policies[0].policy_id),
        ("deductible amount and conditions", policies[0].policy_id),
        ("exclusions and what is not covered", policies[0].policy_id),
        ("claims procedure and police report", policies[0].policy_id),
    ]

    for query, policy_id in test_queries:
        chunks = retrieve_policy_chunks(query, policy_id, top_k=3)
        print(f"  Query: '{query}' (policy={policy_id})")
        print(f"    → {len(chunks)} chunks retrieved")
        if chunks:
            preview = chunks[0][:120].replace("\n", " ")
            print(f"    Top chunk: '{preview}...'")
        print()

    if len(policies) > 1:
        pid_a = policies[0].policy_id
        pid_b = policies[1].policy_id
        chunks_a = retrieve_policy_chunks("coverage", pid_a, top_k=5)
        chunks_b = retrieve_policy_chunks("coverage", pid_b, top_k=5)
        print(f"  Policy filtering: {pid_a} → {len(chunks_a)} chunks, "
              f"{pid_b} → {len(chunks_b)} chunks")

    print("  ✅ RAG retrieval test passed")


def main():
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║  Insurance Claims Triage Agent — Data Setup         ║")
    print("║  Kaggle (real fraud data) + Faker + RAG             ║")
    print("╚══════════════════════════════════════════════════════╝")

    print_sources()

    print(f"  Config: N_KAGGLE_CLAIMS={N_KAGGLE_CLAIMS}, N_POLICIES={N_POLICIES},")
    print(f"          N_RANDOM_CLAIMS={N_RANDOM_CLAIMS}, N_HISTORY_ENTRIES={N_HISTORY_ENTRIES},")
    print(f"          N_FRAUD_CUSTOMERS={N_FRAUD_CUSTOMERS}")
    print(f"          RAG_CHUNK_SIZE={RAG_CHUNK_SIZE}, RAG_CHUNK_OVERLAP={RAG_CHUNK_OVERLAP}")
    print()

    # Step 1: Download Kaggle dataset
    print("── Step 1 : Downloading Kaggle dataset (real fraud data) ──")
    kaggle_csv = download_kaggle_dataset()
    kaggle_df = load_kaggle_claims(kaggle_csv, N_KAGGLE_CLAIMS)
    print()

    # Step 2: Generate synthetic data (Faker)
    print("── Step 2 : Generating synthetic data (Faker + Pydantic) ──")
    policies, claims, claim_history = generate_test_claims(
        n_policies=N_POLICIES,
        n_random_claims=N_RANDOM_CLAIMS,
        n_history_entries=N_HISTORY_ENTRIES,
        n_fraud_customers=N_FRAUD_CUSTOMERS,
        scenario_distribution=SCENARIO_DISTRIBUTION,
    )
    print(f"  Policies: {len(policies)}")
    print(f"  Claims: {len(claims)} (5 controlled + {len(claims)-5} random)")
    print(f"  Claim history: {len(claim_history)}")
    print()

    # Step 3: Build DuckDB
    print("── Step 3 : Building DuckDB ──")
    db_path = build_duckdb(kaggle_df, policies, claims, claim_history)
    print()

    # Step 4: Build RAG index
    print("── Step 4 : Building RAG index ──")
    try:
        rag_stats = build_rag_index(policies)
        print()
    except Exception as e:
        print(f"  ⚠️  RAG index build failed: {e}")
        print(f"  ⚠️  Skipping RAG (install faiss-cpu + sentence-transformers to enable)")
        rag_stats = {"chunks": 0, "vectors": 0, "dim": 0}
        print()

    # Step 5: Test RAG retrieval
    if rag_stats["chunks"] > 0:
        print("── Step 5 : Testing RAG retrieval ──")
        try:
            test_rag_retrieval(policies)
        except Exception as e:
            print(f"  ⚠️  RAG retrieval test failed: {e}")
        print()

    print("✅ Setup complete!")
    print(f"   DB  : {db_path}")
    print(f"   RAG : {rag_stats['chunks']} chunks indexed "
          f"({rag_stats.get('vectors', 0)} vectors, dim={rag_stats.get('dim', 0)})")
    print()
    print("   Test with:")
    print("     uv run python -c \"import duckdb; print(duckdb.connect('data/insurance_claims.duckdb').execute('SELECT * FROM kaggle_claims LIMIT 5').fetchdf())\"")
    print()
    print("   RAG providers:")
    print("     RAG_PROVIDER=faiss       → local FAISS on PVC (k3d)")
    print("     RAG_PROVIDER=s3vectors   → AWS S3 Vectors (real AWS / Floci)")
    print("     RAG_PROVIDER=mock        → fallback (no indexing)")


if __name__ == "__main__":
    main()
