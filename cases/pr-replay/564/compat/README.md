Synthetic case, not a real PR tree. PR 564 (the maintainer's complaint about a blocking ADC read) is represented by `port.patch`, applied to a copy of the
base tree: TemperatureControl::on_second_tick busy-waits about 2 ms for an ADC conversion with a us_ticker_read loop and no wait_* call.
The checker must flag it by the busy-loop rule (static) and by the handler-duration check (runtime, no allow-list entry).
