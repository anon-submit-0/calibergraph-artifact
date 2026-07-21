select *
from (
  values
    (1, 101, date '2026-01-01', 'direct', 'US', 120.0, 2),
    (2, 102, date '2026-01-01', 'paid_search', 'US', 80.0, 1),
    (3, 103, date '2026-01-02', 'email', 'CA', 40.0, 1),
    (4, 101, date '2026-01-03', 'paid_search', 'US', 160.0, 3)
) as t(order_id, customer_id, order_date, channel, country, revenue, units)
