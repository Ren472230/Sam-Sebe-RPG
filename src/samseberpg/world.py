LOCATION_GRAPH: dict[str, set[str]] = {
    "workshop_yard": {"village_square"},
    "village_square": {"workshop_yard", "river_edge"},
    "river_edge": {"village_square"},
}
