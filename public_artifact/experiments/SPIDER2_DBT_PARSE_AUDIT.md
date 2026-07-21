# release Spider2-DBT dbt Parse Audit

This audit runs dbt parse on the official Spider2-DBT project files as third-party project-level semantic assets. It does not claim full Spider-Agent LLM task solving or official leaderboard submission.

Source: https://github.com/xlang-ai/Spider2 @ `01a4c67c1e3f6ab9032716b050a927abbb245f65`

Projects: 69; parse pass: 46; fail: 23; timeout: 0
YAML files: 2046; SQL files: 10007; model entries: 3589; source entries: 78; column tests: 2331; metric-like columns: 4049

| instance | parse | yaml | sql | models | sources | tests | metric-like cols | message |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| activity001 | fail | 27 | 124 | 62 | 0 | 20 | 7 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| airbnb001 | pass | 22 | 159 | 64 | 1 | 43 | 13 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| airbnb002 | fail | 22 | 159 | 64 | 1 | 49 | 15 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| airport001 | pass | 18 | 99 | 44 | 1 | 30 | 10 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| analytics_engineering001 | pass | 6 | 27 | 3 | 1 | 11 | 2 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| app_reporting001 | fail | 87 | 328 | 102 | 2 | 2 | 102 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| app_reporting002 | pass | 86 | 329 | 100 | 2 | 2 | 100 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| apple_store001 | pass | 48 | 225 | 69 | 1 | 0 | 25 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| asana001 | pass | 41 | 193 | 75 | 1 | 57 | 44 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| asset001 | pass | 4 | 8 | 6 | 1 | 14 | 4 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| atp_tour001 | pass | 19 | 151 | 58 | 1 | 38 | 15 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| biketheft001 | fail | 18 | 110 | 47 | 1 | 26 | 9 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| chinook001 | fail | 32 | 156 | 66 | 1 | 88 | 17 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| danish_democracy_data001 | pass | 20 | 130 | 71 | 1 | 71 | 7 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| divvy001 | fail | 5 | 1 | 3 | 2 | 11 | 1 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| f1001 | fail | 18 | 143 | 48 | 1 | 22 | 8 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| f1002 | fail | 18 | 139 | 47 | 1 | 26 | 10 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| f1003 | fail | 18 | 143 | 48 | 1 | 31 | 8 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| flicks001 | fail | 21 | 119 | 48 | 1 | 9 | 7 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| gitcoin001 | pass | 4 | 9 | 10 | 1 | 20 | 3 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| google_ads001 | pass | 48 | 195 | 62 | 1 | 21 | 49 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| google_play001 | pass | 48 | 215 | 69 | 1 | 2 | 72 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| google_play002 | fail | 49 | 215 | 63 | 1 | 2 | 29 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| greenhouse001 | pass | 44 | 251 | 94 | 1 | 62 | 125 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| hive001 | pass | 5 | 0 | 2 | 1 | 8 | 2 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| hubspot001 | pass | 62 | 347 | 127 | 1 | 122 | 110 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| intercom001 | pass | 39 | 190 | 65 | 1 | 32 | 31 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| inzight001 | fail | 36 | 252 | 59 | 1 | 244 | 10 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| jira001 | pass | 49 | 229 | 82 | 1 | 57 | 73 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| lever001 | pass | 40 | 233 | 86 | 1 | 46 | 53 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| marketo001 | pass | 49 | 221 | 80 | 1 | 63 | 61 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| maturity001 | fail | 23 | 133 | 62 | 2 | 54 | 11 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| movie_recomm001 | pass | 3 | 6 | 7 | 0 | 16 | 1 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| mrr001 | pass | 6 | 5 | 3 | 1 | 28 | 7 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| mrr002 | pass | 6 | 4 | 3 | 1 | 28 | 7 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| nba001 | pass | 6 | 111 | 16 | 4 | 35 | 8 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| netflix001 | fail | 6 | 5 | 2 | 1 | 3 | 1 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| pendo001 | pass | 48 | 239 | 97 | 1 | 32 | 158 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| playbook001 | pass | 5 | 1 | 1 | 1 | 7 | 5 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| playbook002 | pass | 5 | 0 | 2 | 1 | 19 | 10 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| provider001 | fail | 4 | 3 | 4 | 1 | 21 | 0 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| qualtrics001 | pass | 47 | 224 | 71 | 1 | 8 | 111 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| quickbooks001 | pass | 41 | 294 | 115 | 1 | 43 | 168 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| quickbooks002 | pass | 41 | 289 | 110 | 1 | 41 | 145 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| quickbooks003 | pass | 41 | 298 | 123 | 1 | 45 | 230 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| recharge001 | fail | 50 | 211 | 66 | 1 | 26 | 62 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| recharge002 | fail | 49 | 218 | 72 | 1 | 32 | 136 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| reddit001 | pass | 4 | 2 | 2 | 1 | 33 | 3 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| retail001 | fail | 6 | 5 | 4 | 1 | 30 | 9 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| salesforce001 | pass | 49 | 195 | 67 | 2 | 40 | 213 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| sap001 | pass | 47 | 219 | 73 | 1 | 0 | 237 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| scd001 | fail | 6 | 12 | 6 | 1 | 17 | 31 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| shopify001 | pass | 60 | 341 | 110 | 1 | 48 | 286 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| shopify002 | pass | 60 | 341 | 109 | 1 | 50 | 262 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| shopify_holistic_reporting001 | fail | 5 | 4 | 6 | 0 | 0 | 82 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| social_media001 | pass | 127 | 224 | 67 | 3 | 22 | 202 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| superstore001 | pass | 5 | 10 | 5 | 1 | 10 | 3 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| synthea001 | pass | 11 | 91 | 60 | 4 | 133 | 66 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| tickit001 | fail | 20 | 124 | 55 | 1 | 50 | 9 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| tickit002 | fail | 20 | 124 | 52 | 1 | 20 | 7 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| tpch001 | pass | 5 | 6 | 2 | 1 | 5 | 6 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| tpch002 | pass | 6 | 6 | 4 | 1 | 7 | 7 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| twilio001 | pass | 48 | 184 | 57 | 1 | 24 | 73 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| workday001 | pass | 31 | 222 | 78 | 1 | 67 | 78 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| workday002 | pass | 31 | 222 | 78 | 1 | 67 | 78 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| xero001 | pass | 38 | 175 | 57 | 1 | 11 | 61 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| xero_new001 | pass | 39 | 173 | 57 | 1 | 11 | 70 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| xero_new002 | pass | 39 | 174 | 55 | 1 | 8 | 49 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
| zuora001 | fail | 5 | 12 | 7 | 0 | 11 | 135 | <python-site-packages>/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl |
