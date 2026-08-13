from pathlib import Path
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService

def make_game(tmp_path: Path, seed=1):
    db=GameDatabase(tmp_path/'game.db'); db.initialize(); db.bootstrap_if_empty(); return db,GameService(db,seed=seed)
def ensure_owned(db,game,item_id):
    if item_id not in db.list_inventory('player_1'):
        assert game.execute(CanonicalAction('player_1',ActionType.TAKE,item_id=item_id)).success
def throw_once(db,game,item_id,target_id,aimed=False):
    ensure_owned(db,game,item_id); return game.execute(CanonicalAction('player_1',ActionType.THROW,item_id=item_id,target_id=target_id,modifiers={'aimed':True} if aimed else {}))

def test_repetition_alone_does_not_unlock_specialization(tmp_path):
    db,game=make_game(tmp_path)
    for _ in range(12): assert throw_once(db,game,'stone_flat_1','target_barrel').success
    assert not db.has_achievement('player_1','hand_remembers_arc') and not db.has_ability('player_1','aimed_throw')
    p=db.fetch_behavior_profile('player_1','throwing'); assert p['attempts']==12 and len(p['targets'])==1 and len(p['projectile_types'])==1 and len(p['locations'])==1

def test_varied_competent_throwing_unlocks_and_persists_aimed_throw(tmp_path):
    db,game=make_game(tmp_path,seed=1)
    for item_id in ['stone_flat_1','stone_round_1']*2: assert throw_once(db,game,item_id,'target_barrel').success
    ensure_owned(db,game,'stone_flat_1'); ensure_owned(db,game,'stone_round_1'); assert game.execute(CanonicalAction('player_1',ActionType.MOVE,destination_id='village_square')).success
    for item_id in ['stone_flat_1','stone_round_1']*2: assert throw_once(db,game,item_id,'target_sign').success
    ensure_owned(db,game,'stone_flat_1'); ensure_owned(db,game,'stone_round_1'); assert game.execute(CanonicalAction('player_1',ActionType.MOVE,destination_id='river_edge')).success
    for item_id in ['stone_flat_1','stone_round_1']*2: assert throw_once(db,game,item_id,'target_post').success
    p=db.fetch_behavior_profile('player_1','throwing'); assert p['attempts']==12 and p['hits']>=5
    assert set(p['targets'])=={'target_barrel','target_sign','target_post'} and set(p['projectile_types'])=={'flat_stone','round_stone'} and set(p['locations'])=={'workshop_yard','village_square','river_edge'}
    assert db.has_achievement('player_1','hand_remembers_arc') and db.has_ability('player_1','aimed_throw')
    reopened=GameDatabase(db.path); assert reopened.has_achievement('player_1','hand_remembers_arc') and reopened.has_ability('player_1','aimed_throw')

def test_aimed_throw_requires_unlock_then_adds_accuracy(tmp_path):
    db,game=make_game(tmp_path,seed=1); ensure_owned(db,game,'stone_flat_1')
    locked=game.execute(CanonicalAction('player_1',ActionType.THROW,item_id='stone_flat_1',target_id='target_barrel',modifiers={'aimed':True})); assert not locked.success and locked.code=='ACTION_NOT_UNLOCKED'
    with db.connect() as conn:
        conn.execute("INSERT INTO abilities(player_id, ability_id, mechanic_json, unlocked_at) VALUES ('player_1','aimed_throw','{\"primitive\":\"MODIFY_ACCURACY\",\"value\":10,\"action\":\"THROW\",\"variant\":\"aimed\"}',0)")
    aimed=game.execute(CanonicalAction('player_1',ActionType.THROW,item_id='stone_flat_1',target_id='target_barrel',modifiers={'aimed':True})); assert aimed.success and aimed.data['accuracy']==0.55

def test_aimed_throw_reads_accuracy_bonus_from_persisted_mechanic(tmp_path):
    db,game=make_game(tmp_path,seed=1); ensure_owned(db,game,'stone_flat_1')
    with db.connect() as conn:
        conn.execute("INSERT INTO abilities(player_id, ability_id, mechanic_json, unlocked_at) VALUES ('player_1','aimed_throw','{\"primitive\":\"MODIFY_ACCURACY\",\"value\":7,\"action\":\"THROW\",\"variant\":\"aimed\"}',0)")
    aimed=game.execute(CanonicalAction('player_1',ActionType.THROW,item_id='stone_flat_1',target_id='target_barrel',modifiers={'aimed':True})); assert aimed.success and aimed.data['accuracy']==0.52
