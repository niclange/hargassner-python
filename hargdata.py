from dataclasses import dataclass
from dataclasses_json import dataclass_json

@dataclass_json
@dataclass(init=True)
class Boiler:
    tmp_eau_ballon: float =0


@dataclass_json
@dataclass(init=True)
class Heater:
    status: int =0
    tmp_chaudiere: float =0
    tmp_fumee: float =0
    reel_retour: float =0
    tmp_ext_moyen: float =0
    puissance: float =0
    minutes_fonct_vis: int =0
    tps_marche_ve: float =0
    nb_mvt_grille: int =0
    tmp_reel_depart: float =0


@dataclass_json
@dataclass(init=True)
class Temperatures:
    tmp_ambiante: float =0
    tmp_ext: float =0
