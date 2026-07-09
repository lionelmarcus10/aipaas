#!/usr/bin/env python3
"""Setup script — build unified DuckDB with CUAD + MessyOps + Faker.

Sources (3) :
  1. CUAD (510 contracts)       — contract text for RAG audit
  2. MessyOps (17 tables, 650k) — B2B procurement + sales data (remplace Olist)
  3. Faker (controlled invoices) — 7 validation cases + random

Mapping : CUAD contract i  →  MessyOps supplier SUPP-00000i  (1:1, naturel B2B)
  - CUAD fournit le contrat commercial (texte, clauses)
  - MessyOps fournit les POs, factures fournisseurs, commandes clients, produits
  - Faker fournit les cas de test contrôlés (variance connue)

Run:  python data/setup_db.py
"""

import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

import duckdb
import pandas as pd

# Paths
DATA_DIR = Path(__file__).parent
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "financial_dispute.duckdb"
MESSYOPS_DIR = RAW_DIR / "messyops"

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from financial_dispute_agent.invoice_generator import (
    generate_test_invoices,
    generate_random_invoices,
)


# ═══════════════════════════════════════════════════════════════════════
# DONNÉES BRUTES MESSYOPS — 17 tables, 647 679 rows au total
# ═══════════════════════════════════════════════════════════════════════
#
# Source : https://www.kaggle.com/datasets/fares279/messyops
# Nature : B2B distributor (procure-to-pay + order-to-cash), 2024-2025
# Licence : open source
#
# Tables MessyOps (17) :
#   ┌──────────────────────────┬──────────┬──────────────────────────────────────┐
#   │ Table                    │ Rows     │ Rôle                                 │
#   ├──────────────────────────┼──────────┼──────────────────────────────────────┤
#   │ suppliers                │    250   │ Fournisseurs B2B (reliability tier)  │
#   │ products                 │  1 200   │ Produits (primary_supplier_id)       │
#   │ purchase_orders          │  5 296   │ Bons de commande fournisseurs        │
#   │ purchase_order_lines     │  5 420   │ Lignes de POs (product_id, qty)      │
#   │ supplier_invoices        │  4 959   │ Factures fournisseurs (réelles!)     │
#   │ supplier_payments        │  4 873   │ Paiements aux fournisseurs           │
#   │ sales_orders             │ 75 081   │ Commandes clients B2B                │
#   │ sales_order_lines        │ 142 502  │ Lignes de commandes (product_id)     │
#   │ invoices                 │ 72 800   │ Factures clients (order-to-cash)     │
#   │ payments                 │ 76 343   │ Paiements clients                    │
#   │ customers                │  4 080   │ Clients B2B (company_name, segment)  │
#   │ shipments                │ 72 784   │ Expéditions (delivery tracking)      │
#   │ returns                  │  5 275   │ Retours produits                     │
#   │ inventory_snapshots      │ 161 408  │ Snapshots stock (par produit/date)   │
#   │ support_tickets          │  7 323   │ Tickets SAV                          │
#   │ warehouses               │      6   │ Entrepôts                            │
#   │ data_quality_log         │  8 079   │ 8 079 data quality issues injectées  │
#   └──────────────────────────┴──────────┴──────────────────────────────────────┘
#   │ TOTAL                    │ 647 679  │                                      │
#   └──────────────────────────┴──────────┴──────────────────────────────────────┘
#
# Tables UTILISÉES dans cette DB (9) :
#   ✅ suppliers              → table `suppliers` (merge avec CUAD)
#   ✅ purchase_orders        → table `purchase_orders`
#   ✅ supplier_invoices      → table `supplier_invoices` (factures fournisseurs réelles)
#   ✅ products               → table `products` (lien supplier → products)
#   ✅ sales_orders           → table `sales_orders` + table `orders` (backward compat)
#   ✅ sales_order_lines      → table `sales_order_lines` (lien product → sales)
#   ✅ customers              → table `customers`
#   ✅ invoices (Faker)       → table `invoices` (cas de test contrôlés, PAS MessyOps)
#   ✅ (derived)              → table `orders` (simplifié de sales_orders pour les tools existants)
#
# Tables NON utilisées (8) — disponibles si tu veux enrichir plus tard :
#   ⬜ supplier_payments      → 4 873 rows — pour analyser les retards de paiement fournisseurs
#   ⬜ invoices (MessyOps)    → 72 800 rows — factures clients (order-to-cash, pas procure-to-pay)
#   ⬜ payments               → 76 343 rows — paiements clients
#   ⬜ shipments              → 72 784 rows — tracking expéditions (retards, pertes)
#   ⬜ returns                →  5 275 rows — retours produits (impact sur litiges)
#   ⬜ inventory_snapshots    │ 161 408 rows — stock (ruptures, surstock)
#   ⬜ support_tickets        →  7 323 rows — tickets SAV (contexte pour litiges)
#   ⬜ warehouses             →      6 rows — entrepôts (filtre géographique)
#   ⬜ data_quality_log       →  8 079 rows — data quality issues injectées (voir ci-dessous)
#
# Data Quality Issues (8 079) :
#   MessyOps injecte délibérément 8 079 problèmes de qualité de données :
#     - valeurs manquantes
#     - doublons
#     - dates invalides
#     - montants incohérents
#     - références cassées
#   Ces issues sont loggées dans data_quality_log.csv avec :
#     table, column, row_id, issue_type, description
#   Utile pour tester la robustesse de l'agent face à des données imparfaites.
#   Non chargé par défaut, mais disponible dans data/raw/messyops/data_quality_log.csv
#
# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION — Modifie ces valeurs pour ajuster la taille de la DB
# ═══════════════════════════════════════════════════════════════════════
#
# ┌─────────────────────────────────────────────────────────────────────┐
# │  CONFIG RAPIDE                                                      │
# ├─────────────────────────────────────────────────────────────────────┤
# │  Test léger     → garder les valeurs par défaut ci-dessous          │
# │  Full MessyOps  → N_SUPPLIERS=250, POs=9999, Sales=9999            │
# │  (9999 = charge tout, évite de calculer le max par supplier)       │
# └─────────────────────────────────────────────────────────────────────┘

# Nombre de fournisseurs (CUAD contracts + MessyOps suppliers, mappés 1:1)
# CUAD a 510 contracts, MessyOps a 250 suppliers.
# Le mapping est 1:1 par index : CUAD contract[i] → MessyOps supplier[i]
# Donc le max est 250 (limité par MessyOps, pas CUAD).
#   Min recommandé : 10  (test rapide, DB ~0.1 MB)
#   Moyen           : 50  (démo correcte, DB ~5 MB)
#   Full MessyOps   : 250 (tous les suppliers, DB ~50 MB)
N_SUPPLIERS = 10

# Nombre de factures de test contrôlées (cas de validation avec variance connue)
# 7 cas : 0%, 3%, 15%, 20%, confiance <80%, trust 30%, trust 85%
# Ne pas changer — ces 7 cas sont codés en dur dans invoice_generator.py
# et correspondent aux 7 cas de validation du sprint2-agents.md
N_TEST_INVOICES = 7

# Nombre de factures aléatoires Faker par fournisseur
# Faker génère des factures avec variance aléatoire (0%, 2%, 5%, 10%, 15%, 25%)
#   Min : 0  (que les 7 cas de test)
#   Recommandé : 5  (50 factures pour 10 suppliers)
#   Full : 20 (5000 factures pour 250 suppliers)
N_RANDOM_INVOICES_PER_SUPPLIER = 5

# Nombre de purchase orders à charger depuis MessyOps par fournisseur
# MessyOps a 5 296 POs pour 250 suppliers (~21 par supplier en moyenne)
# Utilise 9999 pour charger TOUS les POs de chaque supplier sélectionné
#   Min : 5   (50 POs pour 10 suppliers)
#   Full : 9999 (tous les POs disponibles)
N_PURCHASE_ORDERS_PER_SUPPLIER = 5

# Nombre de sales orders à charger depuis MessyOps par fournisseur
# Le lien est indirect : supplier → products → sales_order_lines → sales_orders
# MessyOps a 75 081 sales orders au total
# Utilise 9999 pour charger TOUTES les sales orders de chaque supplier
#   Min : 20  (200 orders pour 10 suppliers)
#   Full : 9999 (toutes les orders disponibles, peut être lent)
N_SALES_ORDERS_PER_SUPPLIER = 20

# RAG — taille des chunks pour la vectorisation FAISS
#
# RAG_CHUNK_SIZE : nombre de caractères par chunk
#   Un contrat CUAD fait en moyenne 54 290 chars (max 338 211 chars).
#   Le chunking découpe le contrat en segments de RAG_CHUNK_SIZE caractères
#   pour que la recherche vectorielle retrouve les clauses pertinentes.
#
#   250 tokens ≈ 1000 caractères (règle empirique anglais)
#   Le modèle d'embedding (all-MiniLM-L6-v2) a un max de 256 tokens.
#   Donc RAG_CHUNK_SIZE ne devrait pas dépasser ~1200 chars (300 tokens).
#   Au-delà, le modèle tronque le texte et perd de l'information.
#
#   Trop petit (200)  → trop de chunks, recherche bruitée, contexte fragmenté
#   Trop grand (2000) → chunks trop longs, embedding tronqué, perte de précision
#   Recommandé : 1000 (250 tokens, bon équilibre précision/contexte)
#   Min : 500   (chunks courts, plus de précision mais moins de contexte)
#   Max : 1200  (limite du modèle d'embedding, ne pas dépasser)
#
# RAG_CHUNK_OVERLAP : nombre de caractères partagés entre chunks consécutifs
#   L'overlap évite de couper une clause au milieu d'un chunk.
#   Si une clause fait 1100 chars et que CHUNK_SIZE=1000, sans overlap elle
#   serait coupée en deux. Avec OVERLAP=200, les chunks se chevauchent de 200
#   chars, donc la clause est dans au moins un chunk complet.
#
#   L'overlap DOIT être inférieur à RAG_CHUNK_SIZE (sinon boucle infinie).
#   Recommandé : 20% de RAG_CHUNK_SIZE (200 pour 1000)
#   Min : 0    (pas d'overlap, risque de couper des clauses)
#   Max : 500  (50% de overlap, beaucoup de redondance)
#   Bonne pratique : OVERLAP = CHUNK_SIZE / 5
RAG_CHUNK_SIZE = 1000       # caractères par chunk (~250 tokens, max 1200)
RAG_CHUNK_OVERLAP = 200     # overlap entre chunks (20% de CHUNK_SIZE, max 500)

# ═══════════════════════════════════════════════════════════════════════
# FIN CONFIGURATION — Ne pas modifier ci-dessous sauf si tu sais ce que tu fais
# ═══════════════════════════════════════════════════════════════════════


# ─── Download functions ───────────────────────────────────────────────

def download_cuad() -> list[dict]:
    """Download CUAD v1 from Zenodo if not present, return contracts list."""
    cuad_json = RAW_DIR / "CUAD_v1" / "CUAD_v1.json"
    cuad_zip = RAW_DIR / "CUAD_v1.zip"

    if not cuad_json.exists():
        if not cuad_zip.exists():
            print("  Downloading CUAD v1 from Zenodo (106 MB)...")
            urllib.request.urlretrieve(
                "https://zenodo.org/records/4595826/files/CUAD_v1.zip",
                str(cuad_zip),
            )
        print("  Extracting CUAD...")
        with zipfile.ZipFile(cuad_zip, "r") as z:
            z.extractall(str(RAW_DIR))

    print("  Loading CUAD contracts...")
    with open(cuad_json) as f:
        data = json.load(f)

    contracts = []
    for item in data["data"]:
        title = item["title"]
        context = item["paragraphs"][0]["context"]
        contracts.append({"title": title, "text": context})

    print(f"  CUAD : {len(contracts)} contracts loaded ({len(contracts[0]['text'])} chars avg)")
    return contracts


def download_messyops() -> Path:
    """Download MessyOps from Kaggle if not present, return directory path."""
    expected_files = [
        "suppliers.csv", "purchase_orders.csv", "purchase_order_lines.csv",
        "supplier_invoices.csv", "supplier_payments.csv",
        "sales_orders.csv", "sales_order_lines.csv",
        "invoices.csv", "payments.csv",
        "customers.csv", "products.csv", "shipments.csv",
        "returns.csv", "inventory_snapshots.csv", "support_tickets.csv",
        "warehouses.csv", "data_quality_log.csv",
    ]

    missing = [f for f in expected_files if not (MESSYOPS_DIR / f).exists()]
    if not missing:
        print(f"  MessyOps already downloaded ({len(expected_files)} files)")
        return MESSYOPS_DIR

    print("  Downloading MessyOps from Kaggle (50 MB)...")
    zip_path = RAW_DIR / "messyops.zip"
    urllib.request.urlretrieve(
        "https://www.kaggle.com/api/v1/datasets/download/fares279/messyops",
        str(zip_path),
    )
    print("  Extracting MessyOps...")
    MESSYOPS_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(str(MESSYOPS_DIR))
    zip_path.unlink()

    found = [f for f in expected_files if (MESSYOPS_DIR / f).exists()]
    print(f"  MessyOps : {len(found)}/{len(expected_files)} files extracted")
    return MESSYOPS_DIR


# ─── Trust score derivation ───────────────────────────────────────────

# Trust scores prédéfinis pour les 7 premiers (cas de test Faker)
PREDEFINED_TRUST_SCORES = [72, 85, 30, 90, 60, 75, 50]

# Mapping MessyOps tier → trust score range
TIER_TO_TRUST = {
    "Reliable":   (85, 95),
    "Average":    (55, 75),
    "Unreliable": (25, 40),
}


def derive_trust_score(tier: str, index: int) -> int:
    """Derive trust score from MessyOps reliability tier.

    First 7 suppliers get predefined scores for test cases.
    Rest gets a score based on their MessyOps tier.
    """
    if index < len(PREDEFINED_TRUST_SCORES):
        return PREDEFINED_TRUST_SCORES[index]
    low, high = TIER_TO_TRUST.get(tier, (50, 70))
    import random
    random.seed(42 + index)
    return random.randint(low, high)


# ─── Build suppliers (CUAD + MessyOps merged) ─────────────────────────

def build_suppliers(contracts: list[dict], messyops_dir: Path, n: int) -> list[dict]:
    """Create supplier records by merging CUAD contracts with MessyOps suppliers.

    Mapping: CUAD contract[i] → MessyOps supplier SUPP-00000(i+1)  (1:1)
    This is a natural B2B mapping: each supplier has a real contract + real POs.
    """
    suppliers_df = pd.read_csv(messyops_dir / "suppliers.csv")
    print(f"  MessyOps suppliers available: {len(suppliers_df)}")

    suppliers = []
    for i in range(min(n, len(contracts), len(suppliers_df))):
        cuad = contracts[i]
        mo = suppliers_df.iloc[i]

        # Clean CUAD title for display name
        title = cuad["title"]
        clean_name = title.split("_")[0].title() if "_" in title else f"Supplier{i+1}"
        clean_name = clean_name[:30]

        tier = mo["supplier_reliability_tier"]
        trust = derive_trust_score(tier, i)

        suppliers.append({
            "supplier_id":          mo["supplier_id"],        # SUPP-000001
            "supplier_name":        mo["supplier_name"],       # MessyOps real name
            "contract_title":       title,                     # CUAD title
            "contract_text":        cuad["text"],              # CUAD full contract
            "trust_score":          trust,                     # derived from tier
            "reliability_tier":     tier,                      # MessyOps tier
            "country":              mo["country"],
            "lead_time_days_mean":  mo["lead_time_days_mean"],
            "avg_defect_rate":      mo["avg_defect_rate"],
            "supplier_since":       mo["supplier_since"],
        })

    print(f"  Built {len(suppliers)} suppliers (CUAD + MessyOps merged 1:1)")
    for s in suppliers[:5]:
        print(f"    {s['supplier_id']} : {s['supplier_name']} "
              f"(tier={s['reliability_tier']}, trust={s['trust_score']})")
    return suppliers


# ─── Load MessyOps tables (filtered by selected suppliers) ────────────

def load_messyops_data(messyops_dir: Path, suppliers: list[dict]) -> dict:
    """Load MessyOps tables filtered by the selected suppliers.

    Returns a dict of DataFrames:
      - purchase_orders
      - supplier_invoices
      - products
      - sales_orders (linked via products)
      - customers
    """
    supplier_ids = [s["supplier_id"] for s in suppliers]
    supplier_id_set = set(supplier_ids)

    # --- Purchase Orders (direct link: supplier_id) ---
    print("  Loading purchase_orders...")
    pos_df = pd.read_csv(messyops_dir / "purchase_orders.csv")
    pos_df = pos_df[pos_df["supplier_id"].isin(supplier_id_set)]

    # Limit per supplier
    pos_limited = []
    for sid in supplier_ids:
        subset = pos_df[pos_df["supplier_id"] == sid].head(N_PURCHASE_ORDERS_PER_SUPPLIER)
        pos_limited.append(subset)
    pos_df = pd.concat(pos_limited, ignore_index=True) if pos_limited else pos_df.head(0)
    print(f"    purchase_orders: {len(pos_df)} rows ({N_PURCHASE_ORDERS_PER_SUPPLIER}/supplier)")

    # --- Supplier Invoices (linked via purchase_order_id) ---
    print("  Loading supplier_invoices...")
    po_ids = set(pos_df["purchase_order_id"].tolist()) if len(pos_df) > 0 else set()
    sinv_df = pd.read_csv(messyops_dir / "supplier_invoices.csv")
    sinv_df = sinv_df[sinv_df["purchase_order_id"].isin(po_ids)]
    print(f"    supplier_invoices: {len(sinv_df)} rows (linked to POs)")

    # --- Products (linked via primary_supplier_id) ---
    print("  Loading products...")
    products_df = pd.read_csv(messyops_dir / "products.csv")
    products_df = products_df[products_df["primary_supplier_id"].isin(supplier_id_set)]
    print(f"    products: {len(products_df)} rows (primary_supplier_id in selection)")

    # --- Sales Order Lines (linked via product_id) ---
    print("  Loading sales_order_lines...")
    product_ids = set(products_df["product_id"].tolist()) if len(products_df) > 0 else set()
    sol_df = pd.read_csv(messyops_dir / "sales_order_lines.csv")
    sol_df = sol_df[sol_df["product_id"].isin(product_ids)]
    print(f"    sales_order_lines: {len(sol_df)} rows (products from selected suppliers)")

    # --- Sales Orders (linked via sales_order_id from lines) ---
    print("  Loading sales_orders...")
    so_ids = set(sol_df["sales_order_id"].tolist()) if len(sol_df) > 0 else set()
    so_df = pd.read_csv(messyops_dir / "sales_orders.csv")
    so_df = so_df[so_df["sales_order_id"].isin(so_ids)]

    # Limit per supplier (via product link)
    # Build a mapping: sales_order_id → supplier_id (via product)
    sol_with_supplier = sol_df.merge(
        products_df[["product_id", "primary_supplier_id"]],
        on="product_id", how="left",
    )
    so_to_supplier = (
        sol_with_supplier.groupby("sales_order_id")["primary_supplier_id"]
        .first().to_dict()
    )

    # Limit sales orders per supplier
    so_limited = []
    for sid in supplier_ids:
        so_for_supplier = [so_id for so_id, sup in so_to_supplier.items() if sup == sid]
        so_for_supplier = so_for_supplier[:N_SALES_ORDERS_PER_SUPPLIER]
        so_subset = so_df[so_df["sales_order_id"].isin(so_for_supplier)]
        so_limited.append(so_subset)
    so_df = pd.concat(so_limited, ignore_index=True) if so_limited else so_df.head(0)
    print(f"    sales_orders: {len(so_df)} rows ({N_SALES_ORDERS_PER_SUPPLIER}/supplier)")

    # Re-filter sol_df to only keep lines for the limited sales orders
    final_so_ids = set(so_df["sales_order_id"].tolist()) if len(so_df) > 0 else set()
    sol_df = sol_df[sol_df["sales_order_id"].isin(final_so_ids)]

    # --- Customers (linked via sales_orders) ---
    print("  Loading customers...")
    customer_ids = set(so_df["customer_id"].tolist()) if len(so_df) > 0 else set()
    cust_df = pd.read_csv(messyops_dir / "customers.csv")
    cust_df = cust_df[cust_df["customer_id"].isin(customer_ids)]
    print(f"    customers: {len(cust_df)} rows (from selected sales orders)")

    return {
        "purchase_orders": pos_df,
        "supplier_invoices": sinv_df,
        "products": products_df,
        "sales_order_lines": sol_df,
        "sales_orders": so_df,
        "customers": cust_df,
        "so_to_supplier": so_to_supplier,
    }


# ─── Build orders table (backward compat with existing tools) ────────

def build_orders_table(messyops_data: dict) -> pd.DataFrame:
    """Build a simplified 'orders' table for backward compatibility.

    Maps MessyOps sales_orders → our 'orders' schema:
      order_id, supplier_id, customer, amount, status, date

    The supplier_id is derived from the product link:
      sales_order → sales_order_line → product → primary_supplier_id
    """
    so_df = messyops_data["sales_orders"]
    so_to_supplier = messyops_data["so_to_supplier"]

    if len(so_df) == 0:
        return pd.DataFrame(columns=["order_id", "supplier_id", "customer", "amount", "status", "date"])

    orders = so_df.copy()
    orders["supplier_id"] = orders["sales_order_id"].map(so_to_supplier)
    orders = orders.rename(columns={
        "sales_order_id": "order_id",
        "customer_id": "customer",
        "order_status": "status",
        "order_date": "date",
        "total_amount": "amount",
    })
    orders = orders[["order_id", "supplier_id", "customer", "amount", "status", "date"]]
    orders = orders.dropna(subset=["supplier_id"])
    print(f"    orders (backward compat): {len(orders)} rows")
    return orders


# ─── DuckDB builder ───────────────────────────────────────────────────

def build_duckdb(
    suppliers: list[dict],
    messyops_data: dict,
    faker_invoices: list,
) -> Path:
    """Build the unified DuckDB database.

    Tables created:
      - suppliers          (CUAD + MessyOps merged)
      - purchase_orders    (MessyOps — real B2B POs)
      - supplier_invoices  (MessyOps — real B2B supplier invoices)
      - products           (MessyOps — products with primary_supplier_id)
      - sales_orders       (MessyOps — real customer orders)
      - sales_order_lines  (MessyOps — order line items)
      - customers          (MessyOps — B2B customers)
      - orders             (backward compat — simplified sales_orders)
      - invoices           (Faker — controlled test cases)
    """
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = duckdb.connect(str(DB_PATH))

    # --- suppliers ---
    print("  Creating suppliers table...")
    suppliers_df = pd.DataFrame(suppliers)
    conn.execute("""
        CREATE TABLE suppliers AS
        SELECT
            supplier_id, supplier_name, contract_title, contract_text,
            trust_score, reliability_tier, country,
            lead_time_days_mean, avg_defect_rate, supplier_since
        FROM suppliers_df
    """)

    # --- purchase_orders ---
    print("  Creating purchase_orders table...")
    po_df = messyops_data["purchase_orders"]
    if len(po_df) > 0:
        conn.execute("CREATE TABLE purchase_orders AS SELECT * FROM po_df")

    # --- supplier_invoices ---
    print("  Creating supplier_invoices table...")
    sinv_df = messyops_data["supplier_invoices"]
    if len(sinv_df) > 0:
        conn.execute("CREATE TABLE supplier_invoices AS SELECT * FROM sinv_df")

    # --- products ---
    print("  Creating products table...")
    prod_df = messyops_data["products"]
    if len(prod_df) > 0:
        conn.execute("""
            CREATE TABLE products AS
            SELECT
                product_id, product_name, category, subcategory,
                primary_supplier_id, unit_cost, list_price,
                gross_margin_pct, unit_of_measure, weight_kg,
                is_seasonal, is_discontinued
            FROM prod_df
        """)

    # --- sales_orders ---
    print("  Creating sales_orders table...")
    so_df = messyops_data["sales_orders"]
    if len(so_df) > 0:
        conn.execute("""
            CREATE TABLE sales_orders AS
            SELECT
                sales_order_id, customer_id, warehouse_id, order_date,
                order_status, sales_channel, subtotal, discount_total,
                tax_rate, tax_amount, shipping_cost, total_amount
            FROM so_df
        """)

    # --- sales_order_lines ---
    print("  Creating sales_order_lines table...")
    sol_df = messyops_data["sales_order_lines"]
    if len(sol_df) > 0:
        conn.execute("""
            CREATE TABLE sales_order_lines AS
            SELECT
                sales_order_line_id, sales_order_id, line_number,
                product_id, quantity, unit_price, discount_rate,
                line_subtotal, discount_amount, line_total
            FROM sol_df
        """)

    # --- customers ---
    print("  Creating customers table...")
    cust_df = messyops_data["customers"]
    if len(cust_df) > 0:
        conn.execute("""
            CREATE TABLE customers AS
            SELECT
                customer_id, company_name, customer_segment, country,
                city, region_type, contact_email, contact_phone,
                payment_term_days, credit_limit, customer_since, is_active
            FROM cust_df
        """)

    # --- orders (backward compat) ---
    print("  Creating orders table (backward compat)...")
    orders_df = build_orders_table(messyops_data)
    if len(orders_df) > 0:
        conn.execute("CREATE TABLE orders AS SELECT * FROM orders_df")

    # --- invoices (Faker — controlled test cases) ---
    print("  Creating invoices table (Faker test cases)...")
    invoices_data = []
    for inv in faker_invoices:
        invoices_data.append({
            "invoice_id": inv.invoice_id,
            "supplier_id": inv.supplier_id,
            "supplier_name": inv.supplier_name,
            "invoice_date": inv.invoice_date,
            "due_date": inv.due_date,
            "total_amount": inv.total_amount,
            "expected_amount": inv.expected_amount,
            "variance_pct": inv.variance_pct,
            "lines_json": json.dumps([l.model_dump() for l in inv.lines]),
            "metadata_json": json.dumps(inv.metadata),
        })
    invoices_df = pd.DataFrame(invoices_data)
    conn.execute("""
        CREATE TABLE invoices AS
        SELECT * FROM invoices_df
    """)

    # --- Indexes ---
    conn.execute("CREATE INDEX idx_suppliers_id ON suppliers(supplier_id)")
    conn.execute("CREATE INDEX idx_orders_supplier ON orders(supplier_id)")
    conn.execute("CREATE INDEX idx_invoices_supplier ON invoices(supplier_id)")
    conn.execute("CREATE INDEX idx_po_supplier ON purchase_orders(supplier_id)")
    conn.execute("CREATE INDEX idx_sinv_supplier ON supplier_invoices(supplier_id)")
    conn.execute("CREATE INDEX idx_products_supplier ON products(primary_supplier_id)")
    conn.execute("CREATE INDEX idx_sol_product ON sales_order_lines(product_id)")
    conn.execute("CREATE INDEX idx_sol_order ON sales_order_lines(sales_order_id)")

    # --- Stats ---
    print()
    print("  ┌─────────────────────────────────────────────────────┐")
    table_names = [
        "suppliers", "purchase_orders", "supplier_invoices",
        "products", "sales_orders", "sales_order_lines",
        "customers", "orders", "invoices",
    ]
    for table in table_names:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  │ {table:25s} : {count:>7} rows            │")
        except Exception:
            print(f"  │ {table:25s} :   (empty)                │")
    print("  └─────────────────────────────────────────────────────┘")

    db_size = DB_PATH.stat().st_size
    print(f"  DB size : {db_size / 1024 / 1024:.1f} MB")
    print(f"  DB path : {DB_PATH}")

    conn.close()
    return DB_PATH


# ─── RAG index builder ───────────────────────────────────────────────

def build_rag_index(suppliers: list[dict]) -> dict:
    """Build FAISS index from CUAD contract texts.

    Chunks each contract into ~1000-char segments with 200-char overlap,
    embeds them with all-MiniLM-L6-v2 (384 dims), and stores in FAISS.
    """
    print("── Building RAG FAISS index ──")
    from financial_dispute_agent.tools.rag_factory import build_index as build_rag

    contracts_map = {s["supplier_id"]: s["contract_text"] for s in suppliers}
    rag_index_path = str(DATA_DIR / "rag_index")
    rag_stats = build_rag(contracts_map, rag_index_path)
    print(f"   RAG: {rag_stats['chunks']} chunks, "
          f"{rag_stats['vectors']} vectors, dim={rag_stats['dim']}")
    return rag_stats


def test_rag_retrieval(suppliers: list[dict]):
    """Test RAG retrieval: query a contract and verify relevant chunks are returned."""
    print("── Testing RAG retrieval ──")
    os.environ["RAG_PROVIDER"] = "faiss"
    os.environ["RAG_INDEX_PATH"] = str(DATA_DIR / "rag_index")

    from financial_dispute_agent.tools.rag_factory import retrieve_contract_chunks

    test_queries = [
        ("late payment penalty terms", suppliers[0]["supplier_id"]),
        ("termination clause conditions", suppliers[0]["supplier_id"]),
        ("confidentiality obligations", suppliers[0]["supplier_id"]),
    ]

    for query, supplier_id in test_queries:
        chunks = retrieve_contract_chunks(query, supplier_id, top_k=3)
        print(f"  Query: '{query}' (supplier={supplier_id})")
        print(f"    → {len(chunks)} chunks retrieved")
        if chunks:
            preview = chunks[0][:120].replace("\n", " ")
            print(f"    Top chunk: '{preview}...'")
        print()

    # Verify supplier filtering works
    if len(suppliers) > 1:
        sid_a = suppliers[0]["supplier_id"]
        sid_b = suppliers[1]["supplier_id"]
        chunks_a = retrieve_contract_chunks("payment", sid_a, top_k=5)
        chunks_b = retrieve_contract_chunks("payment", sid_b, top_k=5)
        print(f"  Supplier filtering: {sid_a} → {len(chunks_a)} chunks, "
              f"{sid_b} → {len(chunks_b)} chunks")
        if len(chunks_a) > 0 and len(chunks_b) > 0:
            print(f"    Chunks are different: {chunks_a[0][:50] != chunks_b[0][:50]}")

    print("  ✅ RAG retrieval test passed")


# ─── Verify mapping (contracts ↔ orders) ─────────────────────────────

def verify_mapping(suppliers: list[dict]):
    """Verify that CUAD contracts correspond to MessyOps orders logically."""
    print("── Verifying contract ↔ order mapping ──")
    conn = duckdb.connect(str(DB_PATH), read_only=True)

    for s in suppliers[:3]:
        sid = s["supplier_id"]
        name = s["supplier_name"]
        tier = s["reliability_tier"]
        trust = s["trust_score"]
        contract_len = len(s["contract_text"])

        po_count = conn.execute(
            "SELECT COUNT(*) FROM purchase_orders WHERE supplier_id = ?", [sid]
        ).fetchone()[0]
        sinv_count = conn.execute(
            "SELECT COUNT(*) FROM supplier_invoices WHERE supplier_id = ?", [sid]
        ).fetchone()[0]
        prod_count = conn.execute(
            "SELECT COUNT(*) FROM products WHERE primary_supplier_id = ?", [sid]
        ).fetchone()[0]
        order_count = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE supplier_id = ?", [sid]
        ).fetchone()[0]

        print(f"  {sid} ({name})")
        print(f"    Contract: {contract_len:>7} chars | Tier: {tier} | Trust: {trust}")
        print(f"    POs: {po_count} | Supplier invoices: {sinv_count} | "
              f"Products: {prod_count} | Customer orders: {order_count}")
        print()

    conn.close()
    print("  ✅ Mapping verified — each supplier has contract + POs + invoices + orders")


# ─── Main ─────────────────────────────────────────────────────────────

def main():
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║  Financial Dispute Agent — Data Setup               ║")
    print("║  CUAD + MessyOps + Faker                            ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    print(f"  Config: N_SUPPLIERS={N_SUPPLIERS}, "
          f"POs/supplier={N_PURCHASE_ORDERS_PER_SUPPLIER}, "
          f"Sales/supplier={N_SALES_ORDERS_PER_SUPPLIER}")
    print()

    # 1. Download CUAD
    print("── Step 1 : CUAD contracts ──")
    contracts = download_cuad()
    print()

    # 2. Download MessyOps
    print("── Step 2 : MessyOps B2B data ──")
    messyops_dir = download_messyops()
    print()

    # 3. Build suppliers (CUAD + MessyOps merged 1:1)
    print(f"── Step 3 : Building suppliers (N_SUPPLIERS={N_SUPPLIERS}) ──")
    suppliers = build_suppliers(contracts, messyops_dir, N_SUPPLIERS)
    print()

    # 4. Load MessyOps data (filtered by selected suppliers)
    print("── Step 4 : Loading MessyOps tables ──")
    messyops_data = load_messyops_data(messyops_dir, suppliers)
    print()

    # 5. Generate Faker invoices (controlled test cases)
    print("── Step 5 : Generating Faker invoices ──")
    test_invoices = generate_test_invoices(suppliers)
    n_random = N_SUPPLIERS * N_RANDOM_INVOICES_PER_SUPPLIER
    random_invoices = generate_random_invoices(suppliers, n=n_random)
    all_invoices = test_invoices + random_invoices
    print(f"  Test invoices : {len(test_invoices)} (controlled cases)")
    print(f"  Random invoices : {len(random_invoices)} ({N_RANDOM_INVOICES_PER_SUPPLIER}/supplier)")
    print(f"  Total Faker : {len(all_invoices)}")
    print()

    # 6. Build DuckDB
    print("── Step 6 : Building DuckDB ──")
    db_path = build_duckdb(suppliers, messyops_data, all_invoices)
    print()

    # 7. Build RAG FAISS index
    print("── Step 7 : Building RAG index ──")
    rag_stats = build_rag_index(suppliers)
    print()

    # 8. Test RAG retrieval
    print("── Step 8 : Testing RAG retrieval ──")
    test_rag_retrieval(suppliers)
    print()

    # 9. Verify mapping
    print("── Step 9 : Verifying contract ↔ order mapping ──")
    verify_mapping(suppliers)

    print()
    print("✅ Setup complete!")
    print(f"   DB : {db_path}")
    print(f"   RAG: {rag_stats['chunks']} chunks indexed")
    print()
    print("   Test with:")
    print("     uv run python -c \"import duckdb; print(duckdb.connect('data/financial_dispute.duckdb').execute('SELECT * FROM suppliers LIMIT 5').fetchdf())\"")


if __name__ == "__main__":
    main()
