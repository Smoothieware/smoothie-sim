PR 633 (Iremitter, 2015) was written for a firmware that had `ON_GCODE_EXECUTE` and `Conveyor::append_gcode`. Edge has neither,
so the module cannot compile as it is. `port.patch` changes only that plumbing: the module runs its trigger from
`on_gcode_received` after draining the queue. The trigger code with the `wait_us` calls and the `us_ticker_read` busy loop
(the lines the maintainer objected to) is untouched. Applied by replay_pr.sh to a copy of the tree (`patch -p1`).
