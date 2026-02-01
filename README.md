# DSC288 Capstone: Multi-Agent LLM Framework for Explainable Financial Decision Support

**Team Members**: Harsh Arya, Gabrielle Despaigne, Camila Paik, Raghav Vasappanavara

## Project Overview

This project develops a multi-agent LLM-based system for financial decision support that prioritizes explainability over pure trading performance. The system provides buy/hold/sell recommendations with natural language explanations grounded in cited sources using RAG.

## Data Sources

All datasets have been downloaded and are located in the `data/raw/` directory.

### 1. Yahoo Finance S&P 500
- Historical data from 1999-2023
- 6,289 trading days
- Source: https://finance.yahoo.com/quote/%5EGSPC/history/
- Location: `data/raw/yahoo_sp500/`

### 2. FNSPID
- Stock prices and financial news for F500 companies
- 7,693 individual stock CSV files + news data
- Source: https://huggingface.co/datasets/Zihan1004/FNSPID
- GitHub: https://github.com/Zdong104/FNSPID_Financial_News_Dataset
- Location: `data/raw/fnspid/`

### 3. Financial Phrasebank
- Financial news sentences with sentiment labels
- 4 agreement levels (50%, 66%, 75%, 100%)
- Source: https://huggingface.co/datasets/takala/financial_phrasebank
- Location: `data/raw/financial_phrasebank/`

### 4. FinQA
- Financial question-answering dataset
- Train, validation, and test splits (~104 MB total)
- Source: https://github.com/czyssrs/FinQA
- Location: `data/raw/finqa/`

## Repository Structure

```
.
├── data/
│   ├── raw/                    # Original downloaded datasets
│   │   ├── yahoo_sp500/
│   │   ├── fnspid/
│   │   ├── financial_phrasebank/
│   │   └── finqa/
│   └── processed/              # Cleaned/processed data (pipeline output)
├── scripts/                    # Data processing scripts
├── notebooks/                  # Jupyter notebooks for EDA
├── requirements.txt            # Python dependencies
└── README.md
```

## References

- FNSPID: https://github.com/Zdong104/FNSPID_Financial_News_Dataset
- Financial Phrasebank: https://huggingface.co/datasets/takala/financial_phrasebank
- FinQA: https://github.com/czyssrs/FinQA
- Yahoo Finance: https://finance.yahoo.com

## License

Educational project for DSC288 Capstone course.
