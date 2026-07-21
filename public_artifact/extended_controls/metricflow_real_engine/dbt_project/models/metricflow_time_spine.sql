-- Standard MetricFlow time spine (required plumbing for the semantic layer).
select cast(range as date) as date_day
from range(date '2022-01-01', date '2027-01-01', interval 1 day)
