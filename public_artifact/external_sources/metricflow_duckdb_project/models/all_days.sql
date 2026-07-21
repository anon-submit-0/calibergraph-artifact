select *
from (
  values
    (date '2026-01-01'),
    (date '2026-01-02'),
    (date '2026-01-03'),
    (date '2026-01-04'),
    (date '2026-01-05'),
    (date '2026-01-06'),
    (date '2026-01-07')
) as t(date_day)
