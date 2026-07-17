"""Phase 8 tests for credential-free local broker configuration."""
import os

import pytest
from fastapi.testclient import TestClient

from backend.broker import broker_settings
from backend.broker.broker_settings import (
    BrokerConfigurationInput,
    create_broker_configuration,
    delete_broker_configuration,
    list_broker_configurations,
    run_mock_connection_test,
    update_broker_configuration,
)
from backend.main import app


def paper_configuration(**overrides):
    values = {
        'name': 'IBKR Paper',
        'broker': 'interactive_brokers',
        'mode': 'paper',
        'host': '127.0.0.1',
        'port': 7497,
        'client_id': 7,
        'profile_label': 'Local paper profile',
    }
    values.update(overrides)
    return BrokerConfigurationInput(**values)


@pytest.fixture
def broker_db(tmp_path):
    return str(tmp_path / 'broker_settings.db')


def test_create_and_list_paper_configuration(broker_db):
    created = create_broker_configuration(paper_configuration(), broker_db)

    assert created['broker'] == 'interactive_brokers'
    assert created['mode'] == 'paper'
    assert created['status'] == 'disconnected'
    assert list_broker_configurations(broker_db) == [created]


def test_mock_test_marks_only_paper_configuration_ready(broker_db):
    created = create_broker_configuration(paper_configuration(), broker_db)

    result = run_mock_connection_test(created['id'], broker_db)

    assert result['test_mode'] == 'mock'
    assert result['status'] == 'paper_ready'
    assert result['configuration']['status'] == 'paper_ready'
    assert result['configuration']['last_mock_tested_at'] is not None


def test_live_configuration_stays_locked_even_when_mock_tested(broker_db):
    created = create_broker_configuration(
        paper_configuration(name='IBKR Live', mode='live', port=7496), broker_db
    )

    result = run_mock_connection_test(created['id'], broker_db)

    assert created['status'] == 'live_locked'
    assert result['test_mode'] == 'mock'
    assert result['status'] == 'live_locked'
    assert 'No IBKR connection was attempted' in result['message']


def test_edit_resets_paper_configuration_to_disconnected(broker_db):
    created = create_broker_configuration(paper_configuration(), broker_db)
    run_mock_connection_test(created['id'], broker_db)

    updated = update_broker_configuration(
        created['id'], paper_configuration(name='Updated paper profile', client_id=8), broker_db
    )

    assert updated['name'] == 'Updated paper profile'
    assert updated['client_id'] == 8
    assert updated['status'] == 'disconnected'
    assert updated['last_mock_tested_at'] is None


def test_remove_configuration_and_restrict_storage_file_permissions(broker_db):
    created = create_broker_configuration(paper_configuration(), broker_db)

    assert os.stat(broker_db).st_mode & 0o077 == 0
    assert delete_broker_configuration(created['id'], broker_db) is True
    assert delete_broker_configuration(created['id'], broker_db) is False
    assert list_broker_configurations(broker_db) == []


def test_broker_configuration_routes_are_crud_and_mock_only(monkeypatch, broker_db):
    monkeypatch.setattr(broker_settings, 'DEFAULT_BROKER_SETTINGS_DB', broker_db)
    client = TestClient(app)
    payload = paper_configuration().model_dump()

    created = client.post('/broker-configurations', json=payload)
    assert created.status_code == 201
    configuration = created.json()

    listed = client.get('/broker-configurations')
    assert listed.status_code == 200
    assert listed.json()['paper_trading_default'] is True
    assert listed.json()['live_trading_enabled'] is False
    assert listed.json()['configurations'][0]['id'] == configuration['id']

    tested = client.post(f"/broker-configurations/{configuration['id']}/test")
    assert tested.status_code == 200
    assert tested.json()['test_mode'] == 'mock'
    assert tested.json()['configuration']['status'] == 'paper_ready'

    payload['name'] = 'Edited API profile'
    updated = client.put(f"/broker-configurations/{configuration['id']}", json=payload)
    assert updated.status_code == 200
    assert updated.json()['name'] == 'Edited API profile'
    assert updated.json()['status'] == 'disconnected'

    deleted = client.delete(f"/broker-configurations/{configuration['id']}")
    assert deleted.status_code == 204
    assert client.get('/broker-configurations').json()['configurations'] == []
