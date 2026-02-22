"""Generates DSC288_Slide_Script.pdf — tight 3-minute version."""
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.enums import TA_LEFT

BG    = colors.HexColor("#1E1E2E")
WHITE = colors.HexColor("#FFFFFF")
YELLOW= colors.HexColor("#F9E2AF")
LGREY = colors.HexColor("#AAAACC")
ACCENT= colors.HexColor("#74C7EC")

def ST(name, sz, col=WHITE, bold=False, italic=False, lh=None, sb=0, sa=4):
    return ParagraphStyle(
        name, fontSize=sz, textColor=col,
        fontName=("Helvetica-Bold" if bold else
                  "Helvetica-Oblique" if italic else "Helvetica"),
        leading=lh or sz*1.4, spaceBefore=sb, spaceAfter=sa,
        backColor=BG)

sTitle = ST("title", 13, YELLOW, bold=True, sb=14, sa=4)
sBody  = ST("body",  11, WHITE,  lh=17, sa=6)
sMeta  = ST("meta",  9,  LGREY, italic=True, sa=10)

def bg_page(canvas, doc):
    canvas.setFillColor(BG)
    canvas.rect(0, 0, *letter, fill=1, stroke=0)

slides = [
    (
        "Slide 1 — Dataset Details",
        "All of our data comes from existing public datasets — nothing was self-generated. "
        "Our primary source is FNSPID, which provided stock price history and financial news "
        "for 100 tickers spanning 2009 to 2023, giving us 262,000 stock-day records. "
        "We also used Financial Phrasebank — 2,264 sentiment-labeled sentences for fine-tuning — "
        "Yahoo Finance S&P 500 data for market context, and FinQA as an evaluation-only benchmark. "
        "Our target is a three-class label — buy, hold, or sell — based on whether the next "
        "day's return crosses a plus or minus two percent threshold.",
        "~45 sec  •  ~95 words"
    ),
    (
        "Slide 2 — Data Pipeline",
        "The pipeline has five sequential stages. Stage one loads all four sources into Parquet. "
        "Stage two cleans duplicates, nulls, and standardizes data types. "
        "Stage three aligns news onto price rows by ticker and date and computes the target label. "
        "Stage four engineers 19 new features. "
        "Stage five does a temporal split — 2009 through 2021 for training, 2022 for validation, "
        "2023 for test — and then normalizes. "
        "The key design choice: all scalers are fitted only on training data and then applied to "
        "validation and test. Forward-fill also runs within each split independently. "
        "No leakage at any step.",
        "~45 sec  •  ~105 words"
    ),
    (
        "Slide 3 — EDA",
        "Four plots drove our feature decisions. "
        "First, the correlation matrix showed that raw OHLC prices are perfectly collinear — "
        "they carry no independent signal — which pushed us toward moving average ratios and "
        "momentum instead. "
        "Second, the target-versus-S&P-direction chart showed that market-up days push buy "
        "probability from 7% to 37%, so we added explicit market direction flags and an excess "
        "return feature. "
        "Third, the returns distribution validated our plus-minus two-percent label thresholds. "
        "And fourth, the univariate distributions confirmed that prices are heavily right-skewed, "
        "which motivated per-ticker normalization rather than a single global scaler.",
        "~50 sec  •  ~105 words"
    ),
    (
        "Slide 4 — Feature Engineering",
        "We engineered 19 features across six categories. "
        "For price context we added SMA-5, 20, and 50, along with price-to-SMA ratios that "
        "tell the model where the current price sits within its own trend. "
        "For momentum we added 5-day and 20-day percent changes. "
        "For risk we added 20-day rolling volatility. "
        "For volume we added a z-score and an abnormal-volume ratio. "
        "And for market context we added excess return and two binary market-direction flags. "
        "All normalization — MinMaxScaler for prices, StandardScaler for volume and returns — "
        "is done per ticker on the training split only.",
        "~45 sec  •  ~100 words"
    ),
]

story = []
for title, body, meta in slides:
    story.append(Paragraph(title, sTitle))
    story.append(Paragraph(body,  sBody))
    story.append(Paragraph(meta,  sMeta))

doc = SimpleDocTemplate(
    r"F:\288r\video documents\DSC288_Slide_Script.pdf",
    pagesize=letter,
    leftMargin=54, rightMargin=54,
    topMargin=50,  bottomMargin=50,
    title="DSC288 Presenter Script",
)
doc.build(story, onFirstPage=bg_page, onLaterPages=bg_page)
print("Saved.")
