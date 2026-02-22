"""
DSC288_Dataset_Slides.pdf  —  4 slides, 16:9 (960×540 pt).
Slides 2 & 4 fill the full page using explicit row heights and generous spacing.
Same content as before — no new sections added.
"""

from PIL import Image as PILImage
from reportlab.lib.pagesizes import landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, PageBreak, Image as RLImage,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import os

PAGE  = (960, 540)
W, H  = PAGE
MX    = 0.38 * inch
MY    = 0.26 * inch
UW    = W - 2 * MX        # ≈ 905 pt
HALF  = (UW - 8) / 2      # ≈ 448 pt

EDA = r"F:\288r\notebooks\eda_outputs"

BG      = colors.HexColor("#1E1E2E")
ACCENT  = colors.HexColor("#74C7EC")
WHITE   = colors.HexColor("#FFFFFF")
LGREY   = colors.HexColor("#AAAACC")
YELLOW  = colors.HexColor("#F9E2AF")
GREEN   = colors.HexColor("#A6E3A1")
PURPLE  = colors.HexColor("#CBA6F7")
PINK    = colors.HexColor("#F38BA8")
ORANGE  = colors.HexColor("#FAB387")
TEAL    = colors.HexColor("#89DCEB")
DARK1   = colors.HexColor("#2A2A3E")
DARK2   = colors.HexColor("#242436")
DARKBLU = colors.HexColor("#111120")

def ST(name, sz, col=WHITE, bold=False, italic=False,
       align=TA_LEFT, lh=None, sb=0, sa=2):
    return ParagraphStyle(
        name, fontSize=sz, textColor=col, alignment=align,
        fontName=("Helvetica-BoldOblique" if bold and italic else
                  "Helvetica-Bold"        if bold           else
                  "Helvetica-Oblique"     if italic         else "Helvetica"),
        leading=lh or sz * 1.35, spaceBefore=sb, spaceAfter=sa, backColor=BG)

sBody = ST("body",  9)
sSm   = ST("sm",    8, LGREY, italic=True, lh=10.5)
sYel  = ST("yel",   9, YELLOW, bold=True)
sH2   = ST("h2",   11, YELLOW, bold=True, sb=6, sa=3)

def P(txt, s=None): return Paragraph(txt, s or sBody)

def img(fname, mw, mh):
    path = os.path.join(EDA, fname)
    with PILImage.open(path) as im:
        iw, ih = im.size
    sc = min(mw / iw, mh / ih)
    return RLImage(path, width=iw * sc, height=ih * sc)

def eda_cell(fname, title_col, title, caption, arrow, feat, mw=HALF, mh=163):
    image = img(fname, mw, mh)
    img_row = Table([[image]], colWidths=[mw],
        style=TableStyle([("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                          ("TOPPADDING",(0,0),(-1,-1),1),("BOTTOMPADDING",(0,0),(-1,-1),1),
                          ("BACKGROUND",(0,0),(-1,-1),DARKBLU)]))
    ann = Table([[Paragraph(
            f'<font color="#{ORANGE.hexval()[2:]}"><b>{arrow}</b></font>'
            f' <font color="#{GREEN.hexval()[2:]}">{feat}</font>',
            ST("an", 7, WHITE, lh=9.5))]],
        colWidths=[mw],
        style=TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#1A2030")),
                          ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
                          ("LEFTPADDING",(0,0),(-1,-1),5),
                          ("LINEABOVE",(0,0),(-1,0),1.0,title_col)]))
    ttl = Paragraph(f'<font color="#{title_col.hexval()[2:]}"><b>{title}</b></font>',
                    ST("t", 8, title_col, bold=True, lh=10, sa=1))
    cap = Paragraph(caption, ST("cp", 7, LGREY, italic=True, lh=9, sa=1))
    return Table([[ttl],[img_row],[cap],[ann]], colWidths=[mw],
        style=TableStyle([("TOPPADDING",(0,0),(-1,-1),1),("BOTTOMPADDING",(0,0),(-1,-1),1),
                          ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))

def row2(left, right):
    return Table([[left, Spacer(8,1), right]], colWidths=[HALF,8,HALF],
        style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                          ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
                          ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))

def slide_header(title, sub=None, col=ACCENT):
    out = [Table([[Paragraph(title,
            ParagraphStyle("sh",fontSize=15,textColor=BG,fontName="Helvetica-Bold",
                           backColor=col,leading=19,spaceAfter=0))]],
        colWidths=[UW],
        style=TableStyle([("BACKGROUND",(0,0),(-1,-1),col),
                          ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                          ("LEFTPADDING",(0,0),(-1,-1),9)]))]
    if sub:
        out.append(Paragraph(sub, ST("sub",7.5,LGREY,italic=True,sb=2,sa=4)))
    else:
        out.append(Spacer(1,3))
    return out

def warn_box(text, col=ORANGE, bg="#2A1A0A", width=None, fs=8.5):
    return Table([[Paragraph(text, ST("w",fs,col,italic=True,lh=fs*1.4))]],
        colWidths=[width or UW],
        style=TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor(bg)),
                          ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
                          ("LEFTPADDING",(0,0),(-1,-1),10),
                          ("LINEABOVE",(0,0),(-1,0),1.2,col)]))

def bg_page(canvas, doc):
    canvas.setFillColor(BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)

story = []

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — Dataset Details
# ══════════════════════════════════════════════════════════════════════════════
story += slide_header("Dataset Details",
    "All data from existing public repositories  •  No self-generated dataset")

story.append(Table([
    [P("Dataset",sYel), P("Source / Citation",sYel),
     P("Role",sYel),    P("Modifications Made",sYel)],
    [P("FNSPID  (Dong et al., 2024)"),
     P("HuggingFace: Zihan1004/FNSPID\narXiv 2402.06698  ·  CC BY-NC 4.0",sSm),
     P("Stock price history (OHLCV)\n+ financial news articles"),
     P("• Full: 7,693 tickers, 28.6M articles → subsetted to first 100 tickers alphabetically\n"
       "• Price history filtered 1962–2023 → 2009-10-07 onward\n"
       "• 159K news matched our 100 tickers; 20K loaded; 9,721 after cleaning\n"
       "• Multi-article days: all articles concatenated into one text field",sSm)],
    [P("Financial Phrasebank  (Malo et al., 2014)"),
     P("HuggingFace: takala/financial_phrasebank\narXiv 1307.5336  ·  CC BY-NC-SA 3.0",sSm),
     P("Sentiment-labeled sentences\nfor model fine-tuning"),
     P("• sentences_allagree config (100% annotator agreement)\n"
       "• 2,264 sentences: neutral 1,391  ·  positive 570  ·  negative 303  ·  used as-is",sSm)],
    [P("Yahoo Finance S&P 500"),
     P("yfinance (^GSPC)  ·  finance.yahoo.com",sSm),
     P("Daily index returns for\nmarket-context features"),
     P("• 6,289 records 1999–2023 → 2009–2023 range used  ·  86.4% stock-day coverage",sSm)],
    [P("FinQA  (Chen et al., 2021)"),
     P("github.com/czyssrs/FinQA\nACL 2021  ·  MIT License",sSm),
     P("Eval-only benchmark for\nnumerical reasoning"),
     P("• 8,281 records: 6,251 train / 883 val / 1,147 test  ·  used as-is",sSm)],
], colWidths=[1.4*inch, 1.65*inch, 1.5*inch, UW-1.4*inch-1.65*inch-1.5*inch],
   style=TableStyle([
       ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
       ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
       ("VALIGN",(0,0),(-1,-1),"TOP"),
       ("FONTNAME",(0,0),(-1,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),8),
       ("TEXTCOLOR",(0,0),(-1,-1),WHITE),
       ("BACKGROUND",(0,0),(-1,0),ACCENT),("TEXTCOLOR",(0,0),(-1,0),BG),
       ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
       ("BACKGROUND",(0,1),(-1,1),DARK1),("BACKGROUND",(0,2),(-1,2),DARK2),
       ("BACKGROUND",(0,3),(-1,3),DARK1),("BACKGROUND",(0,4),(-1,4),DARK2),
   ])))

story.append(Spacer(1,5))
story.append(P("Dataset Metadata", sH2))

meta_left = Table([
    [P("Property",sYel),      P("Value",sYel)],
    [P("Total records"),      P("262,257 stock-day records  (one row = one ticker × one trading day)")],
    [P("Tickers"),            P("100  (first 100 alphabetically from FNSPID's universe of 7,693)")],
    [P("Date range"),         P("Oct 2009 – Dec 2023  (14.2 years of trading days)")],
    [P("Target classes (3)"), P("buy  /  hold  /  sell   (next-day return at ±2% bands)")],
    [P("Class distribution"), P("hold 57.7%  ·  buy 21.8%  ·  sell 20.4%")],
    [P("Total features"),     P("35  (16 original  +  19 engineered)")],
    [P("Storage format"),     P("Apache Parquet  (per-stage checkpoint files)")],
], colWidths=[1.15*inch, HALF-1.15*inch-4],
   style=TableStyle([
       ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
       ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
       ("VALIGN",(0,0),(-1,-1),"TOP"),
       ("FONTNAME",(0,0),(-1,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),8),
       ("TEXTCOLOR",(0,0),(-1,-1),WHITE),
       ("BACKGROUND",(0,0),(-1,0),ACCENT),("TEXTCOLOR",(0,0),(-1,0),BG),
       ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
   ] + [("BACKGROUND",(0,i),(-1,i),DARK1 if i%2==1 else DARK2) for i in range(1,8)]))

meta_right = Table([
    [P("Field type",sYel),          P("Columns",sYel),                                   P("Dtype",sYel)],
    [P("Price  (OHLCV)"),           P("open, high, low, close, adj_close, volume"),       P("float64 / int64")],
    [P("Identifiers"),              P("ticker, date"),                                    P("string / date")],
    [P("News"),                     P("news_text, news_count"),                           P("string / int")],
    [P("Market context"),           P("sp500_return, market_up, market_down"),            P("float / binary")],
    [P("Technical indicators (9)"), P("sma_5/20/50, momentum_5/20, volatility_20,\nvolume_ratio, price_to_sma5/20"), P("float64")],
    [P("Normalized features (6)"),  P("open/high/low/close_norm, volume_norm,\nreturn_norm, excess_return"),         P("float64")],
    [P("Target"),                   P("target  (buy / hold / sell)"),                     P("string")],
], colWidths=[1.3*inch, HALF*0.615, HALF-1.3*inch-HALF*0.615-4],
   style=TableStyle([
       ("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),
       ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
       ("VALIGN",(0,0),(-1,-1),"TOP"),
       ("FONTNAME",(0,0),(-1,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),8),
       ("TEXTCOLOR",(0,0),(-1,-1),WHITE),
       ("BACKGROUND",(0,0),(-1,0),ACCENT),("TEXTCOLOR",(0,0),(-1,0),BG),
       ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
   ] + [("BACKGROUND",(0,i),(-1,i),DARK1 if i%2==1 else DARK2) for i in range(1,8)]))

story.append(Table([[meta_left, Spacer(8,1), meta_right]], colWidths=[HALF,8,HALF],
    style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                      ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
                      ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)])))

story.append(Spacer(1,4))
story.append(warn_box("⚠  Ticker note: first 100 alphabetically (A, AA, AAAU … ADSK, ADSW) — "
    "heterogeneous mix of large, mid, and small-cap stocks; not specifically Fortune 500."))
story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — Data Pipeline
# Row heights force the table to fill the page vertically.
# ══════════════════════════════════════════════════════════════════════════════
story += slide_header("Data Pipeline: Cleansing & Augmentation",
    "5-stage sequential pipeline  •  Leakage-free by design  •  ~3 min runtime")

# Available height after header+subtitle+spacer+warning ≈ 422 pt for the table
# 6 rows (1 header + 5 data).  Header: 24 pt.  Each data row: (422-24)/5 ≈ 80 pt
PIPE_HDR_H  = 24
PIPE_ROW_H  = 80

sc_list = [ACCENT, GREEN, YELLOW, PURPLE, PINK]
stages = [
    ("Stage 1","Load",
     "Pulls all four raw sources into standardized Apache Parquet using the HuggingFace "
     "datasets library and yfinance. Normalizes column names across all sources "
     "(Stock_symbol → ticker, Date → date). Enforces consistent dtypes. "
     "Writes one Parquet file per source as a reproducible checkpoint.",
     "4 raw Parquet files\n(prices, news, sp500, finqa)"),
    ("Stage 2","Clean",
     "Removes exact-duplicate rows. Normalizes date formats to UTC-aware timestamps for news. "
     "Resolves nulls — publisher/author fully null in FNSPID news (kept, flagged). "
     "Only 1 null in adj_close and 1 in sp500_return. "
     "Removes price outlier records; enforces float64 for all numeric columns.",
     "Clean Parquets\nnull report · dtype-validated"),
    ("Stage 3","Temporal Alignment",
     "Left-joins news onto price rows by (ticker, date) — 1.46% of stock-days have news. "
     "Multiple articles on the same day are concatenated into one text field; news_count tracks quantity. "
     "Joins S&P 500 returns by date (86.4% coverage). "
     "Thresholds next-day return at ±2% → buy / hold / sell target label.",
     "262,257 aligned records\nbuy / hold / sell target"),
    ("Stage 4","Feature Engineering",
     "Adds 9 technical indicators: SMA-5/20/50, price-to-SMA-5/20 ratios, "
     "5-day and 20-day momentum, 20-day rolling volatility, and volume ratio (today ÷ 20-day avg). "
     "Adds 3 market-relative features: excess_return, market_up flag, market_down flag. "
     "Normalization deliberately deferred to Stage 5 — no look-ahead possible here.",
     "35 features per record\n(pre-normalization)"),
    ("Stage 5","Split & Normalize",
     "Temporal train/val/test split: Train 2009–2021 · Val 2022 · Test 2023. "
     "MinMaxScaler for prices and StandardScaler for volume/returns, "
     "both fitted on training data only — transform applied to val/test. "
     "Forward-fill applied within each split independently so val/test gaps "
     "cannot propagate into training rows.",
     "Train ~215K\nVal ~18K  ·  Test ~18K"),
]

pipe_rows = [[
    P("",sYel),
    Paragraph("Stage", ParagraphStyle("ph",fontSize=9,textColor=BG,fontName="Helvetica-Bold",backColor=BG,leading=12)),
    P("Description",sYel),
    P("Output",sYel),
]]
for i,(tag,title,desc,out) in enumerate(stages):
    sc = sc_list[i]
    pipe_rows.append([
        Paragraph(f'<font color="#{sc.hexval()[2:]}">●</font>',
                  ST(f"dot{i}",12,sc,lh=15)),
        Paragraph(f'<font color="#{sc.hexval()[2:]}"><b>{tag}</b>\n{title}</font>',
                  ST(f"tt{i}",9.5,sc,bold=False,lh=13)),
        P(desc, ST(f"d{i}", 9.5, WHITE, lh=13.5)),
        P(out,  ST(f"o{i}", 9,   GREEN, lh=12.5)),
    ])

pipe_style = TableStyle([
    ("TOPPADDING",    (0,0),(-1,-1), 10), ("BOTTOMPADDING",(0,0),(-1,-1), 10),
    ("LEFTPADDING",   (0,0),(-1,-1), 6),  ("RIGHTPADDING", (0,0),(-1,-1), 6),
    ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ("FONTNAME",      (0,0),(-1,-1), "Helvetica"),
    ("FONTSIZE",      (0,0),(-1,-1), 9.5),
    ("TEXTCOLOR",     (0,0),(-1,-1), WHITE),
    ("BACKGROUND",    (0,0),(-1,0),  ACCENT),
    ("TEXTCOLOR",     (0,0),(-1,0),  BG),
    ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
] + [("BACKGROUND",(0,i),(-1,i), DARK1 if i%2==1 else DARK2) for i in range(1,6)]
  + [("LINEABOVE",(0,i),(-1,i), 0.5, colors.HexColor("#3A3A5E")) for i in range(1,6)])

story.append(Table(pipe_rows,
    colWidths=[0.22*inch, 0.9*inch,
               UW - 0.22*inch - 0.9*inch - 1.7*inch, 1.7*inch],
    rowHeights=[PIPE_HDR_H] + [PIPE_ROW_H]*5,
    style=pipe_style))

story.append(Spacer(1, 7))
story.append(warn_box(
    "⚠  Leakage prevention: MinMaxScaler & StandardScaler fitted on training split only.  "
    "Forward-fill applied within each split independently.  "
    "Normalization deferred until after temporal split — no look-ahead possible.",
    col=GREEN, bg="#1A2A1A", fs=9))

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — EDA Visualizations (2×2 grid)
# ══════════════════════════════════════════════════════════════════════════════
story += slide_header("EDA: Key Visualizations that Drove Feature Selection",
    "4 most impactful plots from 7 produced  (notebooks/eda_outputs/)")

MH = 163

c_corr = eda_cell("05_correlation_matrix.png", PURPLE,
    "Feature Correlation Matrix",
    "OPEN/HIGH/LOW/CLOSE perfectly collinear (r=1.00). Volume ≈ 0. "
    "sp500_return → next_day_return r = 0.60 — dominant raw signal.",
    "→ Raw OHLC are redundant as independent features.",
    "Price-to-SMA ratios & momentum added instead. "
    "sp500_return dominance → excess_return, market_up, market_down.")

c_tgt = eda_cell("07_target_relationships.png", PINK,
    "Target Distribution by S&P 500 Direction",
    "S&P Up days: buy=37%, sell=6%.  S&P Down days: buy=7%, sell=36%. "
    "News vs no-news shows no significant label shift.",
    "→ S&P 500 direction is the strongest contextual signal.",
    "market_up / market_down flags added. "
    "excess_return isolates stock alpha from market movement.")

c_ret = eda_cell("03_returns_distribution.png", GREEN,
    "Next-Day Returns Distribution  (±2% label thresholds)",
    "Returns approximately normal, centered near 0. ±2% bands validated as non-trivial moves. "
    "Box plot confirms outliers extend to ±15%.",
    "→ ±2% thresholds chosen from this distribution.",
    "volatility_20 (rolling 20-day std) added — captures when extreme moves are likely.")

c_uni = eda_cell("02_univariate_distributions.png", ACCENT,
    "Univariate Price Distributions  &  Target Class Balance",
    "All OHLC prices heavily right-skewed (median ~$364, mean ~$799). "
    "Target: hold 57.7% · buy 21.8% · sell 20.4% — mild class imbalance.",
    "→ Global normalization would distort cross-ticker comparisons.",
    "Per-ticker MinMaxScaler chosen. "
    "Mild imbalance manageable via class weights if needed.")

story.append(row2(c_corr, c_tgt))
story.append(Spacer(1, 5))
story.append(row2(c_ret,  c_uni))
story.append(PageBreak())

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — Feature Engineering
# Single full-width table for features, simple 2-cell bottom strip for
# split strategy and normalization. No nested tables.
# ══════════════════════════════════════════════════════════════════════════════
story += slide_header("Feature Engineering: What We Built & Why",
    "16 original columns  →  35 total features  (19 engineered)  •  All decisions EDA-driven")

# Available height ≈ 462 pt
# Feature table: 9 rows × 43 pt = 387 pt
# Gap: 8 pt
# Bottom strip: 67 pt
# Total: 462 pt ✓
F_HDR = 25
F_ROW = 43
F_C1  = 1.3 * inch   # Category
F_C2  = 1.8 * inch   # Features
F_C3  = UW - F_C1 - F_C2  # EDA motivation

def FP(txt, col=WHITE, bold=False, sz=9):
    return Paragraph(txt, ST(f"fp{txt[:4]}", sz, col, bold=bold, lh=sz*1.35))

feat_rows = [
    [FP("Category",    YELLOW, bold=True),
     FP("Feature(s)",  YELLOW, bold=True),
     FP("Why  —  EDA finding that motivated it", YELLOW, bold=True)],

    [FP("Price Normalization  (6)"),
     FP("open_norm, high_norm,\nlow_norm, close_norm,\nvolume_norm, return_norm"),
     FP("OHLC prices are heavily right-skewed and vary enormously across tickers "
        "(e.g. a $5 stock vs $20,000 Berkshire share). "
        "Per-ticker MinMaxScaler [0–1] on prices; StandardScaler z-score on volume and returns. "
        "Scalers fitted on training data only — no leakage.")],

    [FP("Moving Averages  (3)"),
     FP("sma_5, sma_20, sma_50"),
     FP("Raw OHLC columns are perfectly collinear (r = 1.00 with each other) so they carry no "
        "independent signal. Moving averages encode short-, medium-, and long-term trend context "
        "that the raw prices cannot provide.")],

    [FP("Price Ratios  (2)"),
     FP("price_to_sma5,\nprice_to_sma20"),
     FP("The model needs to know where the current price sits relative to its own trend, "
        "not its absolute dollar value. These ratios are scale-invariant across tickers "
        "and across the full 14-year time span.")],

    [FP("Momentum  (2)"),
     FP("momentum_5, momentum_20\n(% change over N days)"),
     FP("The correlation matrix showed consistent directional signal for both 5-day and 20-day windows. "
        "Momentum captures rate-of-change information that is absent from static SMA levels.")],

    [FP("Volatility  (1)"),
     FP("volatility_20\n(rolling 20-day std of returns)"),
     FP("The returns distribution showed outliers extending to ±15%, with 1.7% of days exceeding ±10% moves. "
        "An explicit volatility feature signals to the model when the environment is turbulent "
        "and large moves are more likely.")],

    [FP("Volume  (2)"),
     FP("volume_norm,\nvolume_ratio  (today ÷ 20-day avg)"),
     FP("Raw volume spans 5 orders of magnitude and is not comparable across tickers. "
        "The z-score normalizes it; the ratio flags days of abnormal trading activity "
        "regardless of a stock's typical absolute volume level.")],

    [FP("Market Context  (3)"),
     FP("excess_return,\nmarket_up, market_down"),
     FP("sp500_return has r = 0.60 with next_day_return — the single strongest raw signal in the dataset. "
        "When the S&P is up, buy probability rises from 7% to 37%. "
        "These three features capture that market-wide context.")],

    [FP("Return Norm  (1)"),
     FP("return_norm\n(StandardScaler per ticker)"),
     FP("Daily return std = 34.7%. The return distribution is symmetric, so StandardScaler "
        "preserves the distribution shape better than MinMax, which would compress the tails.")],
]

feat_style = TableStyle([
    ("TOPPADDING",    (0,0),(-1,-1), 5),   ("BOTTOMPADDING",(0,0),(-1,-1), 5),
    ("LEFTPADDING",   (0,0),(-1,-1), 8),   ("RIGHTPADDING", (0,0),(-1,-1), 8),
    ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ("FONTNAME",      (0,0),(-1,-1), "Helvetica"),
    ("FONTSIZE",      (0,0),(-1,-1), 9),
    ("TEXTCOLOR",     (0,0),(-1,-1), WHITE),
    ("BACKGROUND",    (0,0),(-1,0),  colors.HexColor("#2A2A50")),
    ("LINEBELOW",     (0,0),(-1,0),  0.8,  ACCENT),
] + [("BACKGROUND",(0,i),(-1,i), DARK1 if i%2==1 else DARK2) for i in range(1,9)]
  + [("LINEBELOW",(0,i),(-1,i),  0.3,  colors.HexColor("#3A3A5E")) for i in range(1,9)])

story.append(Table(feat_rows,
    colWidths=[F_C1, F_C2, F_C3],
    rowHeights=[F_HDR] + [F_ROW]*8,
    style=feat_style))

story.append(Spacer(1, 8))

# ── Bottom strip: split strategy (left) | normalization (right) ───────────────
bottom = Table([[
    Paragraph(
        '<font color="#F9E2AF"><b>Temporal Split</b></font>   '
        'Train: Oct 2009–Dec 2021 (~215K)  ·  '
        'Val: Jan–Dec 2022 (~18K)  ·  '
        'Test: Jan–Dec 2023 (~18K)',
        ST("bs1", 9.5, WHITE, lh=14)),
    Paragraph(
        '<font color="#F9E2AF"><b>Normalization</b></font>   '
        'OHLC prices → MinMaxScaler [0,1] per ticker  ·  '
        'Volume &amp; Returns → StandardScaler (z-score) per ticker  ·  '
        'All scalers fitted on training split only',
        ST("bs2", 9.5, WHITE, lh=14)),
]], colWidths=[UW/2 - 4, UW/2 - 4],
   style=TableStyle([
       ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#1A2A1A")),
       ("TOPPADDING",    (0,0),(-1,-1), 14), ("BOTTOMPADDING",(0,0),(-1,-1), 14),
       ("LEFTPADDING",   (0,0),(-1,-1), 12), ("RIGHTPADDING", (0,0),(-1,-1), 12),
       ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
       ("LINEABOVE",     (0,0),(-1,0),  1.2, GREEN),
       ("LINEBEFORE",    (1,0),(1,-1),  0.5, colors.HexColor("#3A5A3A")),
   ]))

story.append(bottom)

# ── Build ─────────────────────────────────────────────────────────────────────
doc = SimpleDocTemplate(
    r"F:\288r\video documents\DSC288_Dataset_Slides.pdf",
    pagesize=PAGE,
    leftMargin=MX, rightMargin=MX,
    topMargin=MY,  bottomMargin=MY,
    title="DSC288 — Dataset & Feature Extraction",
)
doc.build(story, onFirstPage=bg_page, onLaterPages=bg_page)
print("Saved.")
