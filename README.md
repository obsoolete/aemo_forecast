# aemo_forecast
An integration to watch for price spikes using AEMO.

## Price forecast data

The `sensor.aemo_forecast_price_forecast` entity exposes the upcoming price as
its state in `$/kWh`. Its `forecast` attribute contains objects with `time` and
`price` fields for use by dashboard cards such as ApexCharts Card.