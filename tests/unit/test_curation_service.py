from src.core.domain.models import POI, Coordinates, CurationList
from src.core.services.curation import CurationService


def test_suggested_curation_lists_for_supported_cities() -> None:
    service = CurationService()
    sp_lists = service.get_suggested_curation_lists("São Paulo")
    assert len(sp_lists) >= 3
    titles = [cl.title for cl in sp_lists]
    assert any("Michelin" in t for t in titles)
    assert any("Cafeterias Especiais" in t for t in titles)

    lima_lists = service.get_suggested_curation_lists("Lima")
    assert len(lima_lists) >= 2
    assert any("50 Best" in cl.title for cl in lima_lists)


def test_apply_curation_boost_to_matching_pois() -> None:
    service = CurationService()
    poi_michelin = POI(
        id="dom",
        name="D.O.M.",
        location=Coordinates(latitude=-23.56, longitude=-46.66),
        utility_score=10.0,
        awards=["Michelin 2 Estrelas"],
    )
    poi_regular = POI(
        id="reg",
        name="Lanchonete Comum",
        location=Coordinates(latitude=-23.56, longitude=-46.66),
        utility_score=5.0,
    )

    custom_list = CurationList(
        id="cl-1",
        title="Meus Favoritos",
        items=[poi_michelin],
    )

    boosted = service.apply_curation_boost([poi_michelin, poi_regular], [custom_list])
    b_dom = next(p for p in boosted if p.id == "dom")
    b_reg = next(p for p in boosted if p.id == "reg")

    # Matched item gets 1.5x boost
    assert b_dom.utility_score == 15.0
    # Regular stays unchanged
    assert b_reg.utility_score == 5.0
