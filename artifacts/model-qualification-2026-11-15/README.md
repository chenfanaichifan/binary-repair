# Model qualification (2026-11-15)

Same 6 cases, same RepairSpec/ABI/semantic-retry flags, same native gate:

| model | verified | key failure classes |
|---|---:|---|
| deepseek-flash | 2/6 | security fail, plan invalid, assembly rejected |
| deepseek-v4-pro | 2/6 | ABI rejected, injection failed, security fail |

The two models verify **different** cases; aggregate funnel only is not enough.
No reference fixes are included in this report.
