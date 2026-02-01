# DSC288 Capstone: Multi-Agent LLM Framework for Explainable Financial Decision Support

**Team Members**: Harsh Arya, Gabrielle Despaigne, Camila Paik, Raghav Vasappanavara

## Project Overview

This project develops a multi-agent LLM-based system for financial decision support that prioritizes explainability over pure trading performance. The system is designed for intermediate and beginner retail investors who value understanding the reasoning behind recommendations.

### Key Features

- **Multi-agent architecture** with role-based financial analysts
- **Explainable recommendations**: Every buy/hold/sell decision includes natural language explanations
- **RAG-based grounding**: All recommendations are grounded in cited sources
- **Comprehensive data integration**: Combines structured market data with unstructured financial text

## Target User

Intermediate/beginner retail investors who value understanding over streamlined numerical systems.

## System Architecture

The system employs specialized agents:
- Fundamental analyst
- News/sentiment analyst  
- Technical analyst
- Optimistic viewpoint agent
- Cautious viewpoint agent

Each agent produces analysis that is combined into a final recommendation with explanations.

## Data Sources

### Downloaded Datasets

1. **Yahoo Finance S&P 500** ✅
   - Historical data from 1999-2023
   - 6,289 trading days
   - Location: `data/raw/yahoo_sp500/`

### Planned Datasets

2. **FNSPID** (In Progress)
   - Stock prices and financial news for F500 companies
   - Source: https://huggingface.co/datasets/Zihan1004/FNSPID
   - Location: `data/raw/fnspid/`

3. **Financial Phrasebank** (In Progress)
   - Financial news sentences with sentiment labels
   - Source: https://huggingface.co/datasets/takala/financial_phrasebank
   - Location: `data/raw/financial_phrasebank/`

4. **FinQA** (In Progress)
   - Financial question-answering dataset
   - Source: https://huggingface.co/datasets/ibm/finqa
   - Location: `data/raw/finqa/`

## Repository Structure

```
.
├── data/
│   ├── raw/                    # Original downloaded datasets
│   │   ├── fnspid/
│   │   ├── financial_phrasebank/
│   │   ├── finqa/
│   │   └── yahoo_sp500/       # ✅ Downloaded
│   └── processed/              # Cleaned/processed data
├── scripts/                    # Data processing scripts
├── notebooks/                  # Jupyter notebooks for EDA
└── requirements.txt           # Python dependencies
```

## Installation

```bash
# Clone the repository
git clone git@github.com:harsh5559/DSC288_Capstone.git
cd DSC288_Capstone

# Install dependencies
pip install -r requirements.txt
```

## Evaluation Metrics

- Temporal consistency of recommendations
- Agreement with rule-based financial baselines
- Faithfulness/grounding of explanations to source data

## Related Work

- **TradingAgents Framework**: https://github.com/TauricResearch/TradingAgents
  - Our project adapts this framework but focuses on explainability rather than trading performance

## References

- FNSPID: https://github.com/Zdong104/FNSPID_Financial_News_Dataset
- Financial Phrasebank: https://huggingface.co/datasets/takala/financial_phrasebank
- FinQA: https://github.com/czyssrs/FinQA
- TradingAgents: https://github.com/TauricResearch/TradingAgents

## License

Educational project for DSC288 Capstone course.
