import pgautofailover_utils as pgautofailover
from nose.tools import *

import os

cluster = None
node1 = None
node2 = None

def setup_module():
    global cluster
    cluster = pgautofailover.Cluster()

def teardown_module():
    cluster.destroy()

def test_000_create_monitor():
    monitor = cluster.create_monitor("/tmp/auth/monitor", authMethod="md5")
    monitor.run()
    monitor.wait_until_pg_is_running()
    monitor.set_user_password("autoctl_node", "autoctl_node_password")

def test_001_init_primary():
    global node1
    node1 = cluster.create_datanode("/tmp/auth/node1", authMethod="md5")
    node1.create()
    node1.config_set("replication.password", "streaming_password")
    node1.run()

    node1.wait_until_pg_is_running()
    node1.set_user_password("pgautofailover_monitor", "monitor_password")

    assert node1.wait_until_state(target_state="single")

def test_002_create_t1():
    node1.run_sql_query("CREATE TABLE t1(a int)")
    node1.run_sql_query("INSERT INTO t1 VALUES (1), (2)")

def test_003_init_secondary():
    global node2
    node2 = cluster.create_datanode("/tmp/auth/node2", authMethod="md5")

    os.putenv('PGPASSWORD', "streaming_password")
    node2.create()
    node2.config_set("replication.password", "streaming_password")

    node2.run()
    assert node2.wait_until_state(target_state="secondary")
    assert node1.wait_until_state(target_state="primary")

def test_004_failover():
    print()
    print("Calling pgautofailover.failover() on the monitor")
    cluster.monitor.failover()
    assert node2.wait_until_state(target_state="primary")
    assert node1.wait_until_state(target_state="secondary")

def test_005_change_replication_passwords():
    node2.config_set("replication.password", "new_streaming_password")
    node1.config_set("replication.password", "new_streaming_password")

    # Test that
    # - the primary has the new password
    # - the secondary can connect using the new password
    # - replication still works

    # TODO: make sure the primary has the new password

    # Restart the secondary to prove it can reconnect with the new password.
    node1.restart_postgres()

    # TODO: wait for replication connection

    node2.run_sql_query("INSERT INTO t1 VALUES (3), (4)")
    print(node1.run_sql_query("SELECT COUNT(*) FROM t1"))
