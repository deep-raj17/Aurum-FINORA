# Load Test Report

**Test Date**: 2026-07-01  
**Test Command**: `locust -f load/locustfile.py --headless -u 5 -r 2 --run-time 30s --host http://localhost:8000`  
**Test Type**: Local Smoke Test  
**Duration**: 30 seconds  
**Environment**: Windows, RTX 4070 12GB VRAM, development workstation

## Summary

| Metric | Value |
|--------|-------|
| Total Requests | 245 |
| Total Failures | 125 |
| Failure Rate | 51.02% |
| Users | 5 |
| Spawn Rate | 2 users/sec |
| Status | Rate Limited |

## Test Configuration

- **Target**: http://localhost:8000 (local)
- **Test Duration**: 30 seconds
- **Concurrent Users**: 5
- **Spawn Rate**: 2 users/second
- **Test Type**: Local smoke test (staging unavailable)

## Results by Endpoint

### Health Endpoint (GET /health)

| Metric | Value |
|--------|-------|
| Requests | 176 |
| Failures | 81 |
| Failure Rate | 46.02% |
| Avg Response Time | 3ms |
| Min Response Time | 1ms |
| Max Response Time | 49ms |
| Median Response Time | 2ms |
| Requests/sec | 6.01 |

**Errors**:
- HTTPError 429 (Too Many Requests): 81 occurrences

### Forecast Endpoint (POST /v1/forecast)

| Metric | Value |
|--------|-------|
| Requests | 69 |
| Failures | 44 |
| Failure Rate | 63.77% |
| Avg Response Time | 26ms |
| Min Response Time | 1ms |
| Max Response Time | 102ms |
| Median Response Time | 3ms |
| Requests/sec | 2.35 |

**Errors**:
- HTTPError 429 (Too Many Requests): 44 occurrences

## Response Time Percentiles

### Health Endpoint

| Percentile | Response Time (ms) |
|-----------|-------------------|
| p50 | 2 |
| p66 | 3 |
| p75 | 3 |
| p80 | 3 |
| p90 | 4 |
| p95 | 4 |
| p98 | 7 |
| p99 | 29 |
| p99.9 | 49 |
| p100 | 49 |

### Forecast Endpoint

| Percentile | Response Time (ms) |
|-----------|-------------------|
| p50 | 3 |
| p66 | 61 |
| p75 | 64 |
| p80 | 67 |
| p90 | 70 |
| p95 | 84 |
| p98 | 99 |
| p99 | 100 |
| p99.9 | 100 |
| p100 | 100 |

### Aggregated

| Percentile | Response Time (ms) |
|-----------|-------------------|
| p50 | 2 |
| p66 | 3 |
| p75 | 3 |
| p80 | 3 |
| p90 | 57 |
| p95 | 67 |
| p98 | 72 |
| p99 | 96 |
| p99.9 | 100 |
| p100 | 100 |

## Analysis

### API Status
- **Health Endpoint**: Responding
- **Forecast Endpoint**: Responding
- **Rate Limiting**: Functional
- **Overall Status**: Running

### Load Test Results
- **Successful Requests**: 120 (48.98%)
- **Rate Limited Requests**: 125 (51.02%)
- **Blocking Issue**: Rate limiting triggered at 5 concurrent users

### Observations
1. API is functional and responding to requests
2. Rate limiting is working correctly (429 responses)
3. Health endpoint has lower latency (3ms avg) vs forecast endpoint (26ms avg)
4. Forecast endpoint shows higher latency variance due to model inference
5. Rate limits are too aggressive for sustained load testing at 5 users

## Staging Status

**Staging Available**: No  
**Staging URL**: Not configured  
**Staging Test**: Blocked  
**Reason**: STAGING_API_URL environment variable not set

## Staging Readiness Assessment

**Status**: PARTIAL - NOT READY FOR STAGING

**Blocking Issues**:
1. STAGING_API_URL not configured
2. Rate limits too aggressive for sustained load testing
3. Sustained load tests (30min, 2hr) not executed

**Non-Blocking Issues**:
- Local smoke test confirms API functionality
- Rate limiting is operational
- Response times are acceptable for successful requests

## Recommendations

### Immediate (Required for Staging)
1. **Configure Staging URL**: Set STAGING_API_URL environment variable
2. **Adjust Rate Limits**: Increase rate limits for staging environment to allow sustained load testing
3. **Run Staging Load Tests**: Execute 5min smoke, 30min sustained, 2hr extended tests on staging

### Secondary (Required for Production)
1. **Load Balancer**: Configure load balancer for production to handle higher concurrency
2. **Rate Limit Strategy**: Implement tiered rate limits based on user tiers
3. **Monitoring**: Add real-time monitoring for rate limit violations
4. **Auto-scaling**: Configure auto-scaling based on request rate

## Conclusion

Local smoke test confirms the API is functional and rate limiting works correctly. However, the current rate limits prevent sustained load testing at even low concurrency (5 users). Staging load testing cannot proceed until STAGING_API_URL is configured and rate limits are adjusted.

**Next Steps**:
1. Deploy staging environment
2. Configure STAGING_API_URL
3. Adjust rate limits for staging
4. Run full load test suite (5min, 30min, 2hr)
5. Document sustained load test results

---

**Report Generated**: 2026-07-01T13:00:00Z  
**Full JSON Report**: `reports/loadtest/local_smoke_load_test.json`
