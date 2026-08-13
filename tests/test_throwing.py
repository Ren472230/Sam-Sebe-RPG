from pathlib import Path
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService

def make_game(tmp_path: Path,name='game.db',seed=11):
    db=GameDatabase(tmp_path/name); db.initialize(); db.bootstrap_if_empty(); return db,GameService(db,seed=seed)
def take(game,item_id): assert game.execute(CanonicalAction('player_1',ActionType.TAKE,item_id=item_id)).success

def test_throw_rejects_item_not_owned(tmp_path):
    db,game=make_game(tmp_path); r=game.execute(CanonicalAction('player_1',ActionType.THROW,target_id='target_barrel',item_id='stone_flat_1'))
    assert not r.success and r.code=='ITEM_NOT_OWNED' and db.fetch_entity('stone_flat_1')['location_id']=='workshop_yard'

def test_throw_rejects_non_projectile(tmp_path):
    db,game=make_game(tmp_path)
    with db.connect() as conn: conn.execute("INSERT INTO entities(entity_id,entity_type,name,location_id,tags_json,state_json) VALUES ('hammer_1','item','Молоток','workshop_yard','[\"tool\"]','{}')")
    take(game,'hammer_1'); r=game.execute(CanonicalAction('player_1',ActionType.THROW,target_id='target_barrel',item_id='hammer_1'))
    assert not r.success and r.code=='ITEM_NOT_THROWABLE' and db.list_inventory('player_1')==['hammer_1']

def test_throw_is_reproducible_with_same_seed(tmp_path):
    _,ga=make_game(tmp_path,'a.db',23); _,gb=make_game(tmp_path,'b.db',23); take(ga,'stone_flat_1'); take(gb,'stone_flat_1')
    a=ga.execute(CanonicalAction('player_1',ActionType.THROW,target_id='target_barrel',item_id='stone_flat_1')); b=gb.execute(CanonicalAction('player_1',ActionType.THROW,target_id='target_barrel',item_id='stone_flat_1'))
    assert a.data['hit']==b.data['hit'] and a.data['accuracy_roll']==b.data['accuracy_roll']

def test_throw_moves_item_back_to_location_and_records_evidence(tmp_path):
    db,game=make_game(tmp_path,seed=3); take(game,'stone_flat_1'); r=game.execute(CanonicalAction('player_1',ActionType.THROW,target_id='target_barrel',item_id='stone_flat_1'))
    assert r.success and db.list_inventory('player_1')==[] and db.fetch_entity('stone_flat_1')['location_id']=='workshop_yard'
    e=db.list_events('player_1')[-1]; assert e['behavior_tags']==['throwing','improvised_projectile']; assert e['evidence']['projectile_type']=='flat_stone'

def test_rng_sequence_survives_service_restart(tmp_path):
    db_a,ga=make_game(tmp_path,'continuous.db',41); db_b,gb=make_game(tmp_path,'restarted.db',41)
    take(ga,'stone_flat_1'); first_a=ga.execute(CanonicalAction('player_1',ActionType.THROW,target_id='target_barrel',item_id='stone_flat_1')); take(ga,'stone_flat_1'); second_a=ga.execute(CanonicalAction('player_1',ActionType.THROW,target_id='target_barrel',item_id='stone_flat_1'))
    take(gb,'stone_flat_1'); first_b=gb.execute(CanonicalAction('player_1',ActionType.THROW,target_id='target_barrel',item_id='stone_flat_1')); restarted=GameService(db_b,seed=999); take(restarted,'stone_flat_1'); second_b=restarted.execute(CanonicalAction('player_1',ActionType.THROW,target_id='target_barrel',item_id='stone_flat_1'))
    assert first_a.data['accuracy_roll']==first_b.data['accuracy_roll'] and second_a.data['accuracy_roll']==second_b.data['accuracy_roll']
