# Bias Dataset Plan for FINORA

This document defines the bias datasets required for production model validation and the analysis plan to detect and mitigate bias in FINORA's financial forecasting and risk models.

## Overview

Financial models can exhibit bias across multiple dimensions including market coverage, geography, asset class, and data sources. This plan identifies critical bias dimensions and defines datasets and analysis methods to measure and mitigate bias.

## Bias Dimensions

### 1. Market Coverage Bias

**Description**: Bias toward certain markets (US vs. international, developed vs. emerging markets).

**Dataset Requirements**:
- Historical coverage by market region (Americas, EMEA, APAC)
- Market capitalization distribution by region
- Trading volume distribution by region
- Data quality scores by region

**Analysis Metrics**:
- Coverage ratio: (number of assets in region / total assets) vs. (market cap in region / global market cap)
- Forecast error distribution by region
- Model performance (MAE, RMSE) by region

**Acceptance Criteria**:
- Coverage ratio deviation < 20% from market cap representation
- Forecast error variance across regions < 1.5x global average
- No region with >2x global average error rate

**Data Sources**:
- World Bank market capitalization data
- Provider coverage reports (Alpha Vantage, Tiingo, Finnhub)
- Internal asset metadata

---

### 2. Geography Bias

**Description**: Bias toward specific countries or economic regions within markets.

**Dataset Requirements**:
- Country-level asset coverage
- GDP-weighted representation
- Currency distribution
- Regulatory regime classification

**Analysis Metrics**:
- Country representation vs. GDP contribution
- Currency bias in forex predictions
- Regulatory regime impact on model performance

**Acceptance Criteria**:
- Top 10 economies by GDP represent >80% of coverage
- No single country exceeds 30% of coverage unless >30% of global market cap
- Currency prediction error variance < 2x across major currencies

**Data Sources**:
- IMF GDP data
- World Bank country classifications
- Provider country coverage data

---

### 3. Language Bias

**Description**: Bias toward English-language news and documentation in sentiment analysis and RAG.

**Dataset Requirements**:
- News article language distribution
- Sentiment model performance by language
- RAG retrieval language distribution
- Translation quality metrics

**Analysis Metrics**:
- Language distribution in training data vs. global financial news
- Sentiment accuracy by language
- RAG retrieval success rate by language

**Acceptance Criteria**:
- English language proportion < 70% of total news corpus
- Sentiment accuracy variance across languages < 15%
- RAG retrieval success rate >80% for top 5 languages

**Data Sources**:
- News provider language metadata
- Multilingual sentiment test sets
- Internal language detection logs

---

### 4. Asset Class Bias

**Description**: Bias toward specific asset classes (equities, fixed income, commodities, crypto, forex).

**Dataset Requirements**:
- Asset class distribution in training data
- Asset class performance metrics
- Sector/industry breakdown within equities
- Fixed income duration/credit quality distribution

**Analysis Metrics**:
- Asset class representation vs. global market allocation
- Forecast accuracy by asset class
- Risk model calibration by asset class

**Acceptance Criteria**:
- Asset class distribution within 20% of global market allocation
- Forecast accuracy variance across asset classes < 1.5x
- Risk model calibration error < 10% across all asset classes

**Data Sources**:
- Global asset allocation benchmarks
- Provider asset class metadata
- Internal asset classification

---

### 5. Large-Cap Bias

**Description**: Bias toward large-capitalization companies vs. small/mid-cap.

**Dataset Requirements**:
- Market cap distribution in training data
- Forecast performance by market cap tier
- Coverage by market cap decile

**Analysis Metrics**:
- Large-cap (>10B USD) proportion vs. market reality
- Forecast error by market cap tier
- Small-cap coverage rate

**Acceptance Criteria**:
- Large-cap proportion < 60% of coverage (vs. ~70% market reality acceptable)
- Forecast error variance across market cap tiers < 2x
- Minimum 20% coverage for mid-cap (1B-10B USD)
- Minimum 10% coverage for small-cap (<1B USD)

**Data Sources**:
- Provider market cap data
- Russell/SPDJI market cap indexes
- Internal asset metadata

---

### 6. News Source Bias

**Description**: Bias toward specific news sources or publication types.

**Dataset Requirements**:
- News source distribution in RAG corpus
- Source reliability scores
- Publication type distribution (press releases, earnings calls, analyst reports)
- Source geographic distribution

**Analysis Metrics**:
- Source concentration (Herfindahl index)
- Sentiment variance by source
- RAG retrieval diversity across sources

**Acceptance Criteria**:
- Herfindahl index < 0.25 (moderate concentration)
- No single source >20% of corpus
- Sentiment variance across sources < 0.15
- Minimum 10 distinct sources for major asset coverage

**Data Sources**:
- News provider source metadata
- Internal source classification
- Credibility scoring systems

---

### 7. Survivorship Bias

**Description**: Bias due to excluding delisted/bankrupt assets from historical data.

**Dataset Requirements**:
- Delisted asset historical data
- Bankruptcy event timeline
- Merger/acquisition history
- Asset lifecycle events

**Analysis Metrics**:
- Survivorship rate in training data
- Backtest performance with vs. without survivorship bias
- Failure prediction accuracy for delisted assets

**Acceptance Criteria**:
- Survivorship-adjusted backtest within 10% of unadjusted results
- Failure prediction AUC >0.65 for delisted assets
- Minimum 5% of training data includes failed/delisted assets

**Data Sources**:
- Delisted asset databases
- Bankruptcy court records
- Provider historical data with delisting

---

## Bias Analysis Pipeline

### Data Collection

1. **Extract bias features** from existing datasets
2. **Augment with external benchmarks** (World Bank, IMF, market indexes)
3. **Create unified bias dataset** with all dimensions

### Analysis Execution

```bash
# Run bias analysis
python scripts/analyze_bias_datasets.py --config config/bias_analysis.yaml --output reports/bias/
```

### Reporting

Bias analysis will produce:

- **JSON Report**: `reports/bias/bias_analysis.json` with all metrics
- **Markdown Report**: `reports/bias/bias_analysis.md` with visualizations
- **Remediation Plan**: Specific actions for failing criteria

---

## Remediation Strategies

### For Coverage Bias

- **Data augmentation**: Add under-represented regions/asset classes
- **Provider expansion**: Onboard additional data providers
- **Synthetic data**: Carefully generated synthetic data for rare classes

### For Performance Bias

- **Model calibration**: Separate calibration by bias dimension
- **Ensemble methods**: Weight models by bias dimension
- **Threshold adjustment**: Different confidence thresholds by class

### For Data Source Bias

- **Source diversification**: Add under-represented sources
- **Source weighting**: Down-weight over-represented sources
- **Adversarial debiasing**: Train to reduce source dependence

---

## Timeline

### Phase 4 (Current)
- Document bias dimensions and acceptance criteria ✅
- Define data collection requirements ✅
- Create analysis pipeline framework ⏳

### Phase 5 (Future)
- Collect bias datasets
- Implement bias analysis pipeline
- Run initial bias analysis
- Document findings and remediation plan

### Phase 6 (Production)
- Continuous bias monitoring
- Automated bias alerts
- Periodic bias audits (quarterly)

---

## Ownership

- **Model Risk Team**: Bias analysis execution and validation
- **Data Platform Team**: Bias dataset collection and maintenance
- **Engineering Team**: Bias analysis pipeline implementation
- **Compliance Team**: Bias acceptance criteria review

---

## References

- **FINORA Model Risk Policy**: docs/MODEL_RISK.md
- **External Validation Matrix**: docs/EXTERNAL_VALIDATION_MATRIX.md
- **Regulatory Guidance**: SR 11-7 (OCC), BCBS 239 (Basel)

---

## Last Updated

- **Date**: 2026-07-01
- **Phase**: Phase 4 - Staging Validation Preparation
- **Status**: Bias dataset plan documented, awaiting dataset collection
