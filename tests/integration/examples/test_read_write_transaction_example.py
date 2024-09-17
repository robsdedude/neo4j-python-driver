# Copyright (c) "Neo4j"
# Neo4j Sweden AB [https://neo4j.com]
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# tag::read-write-transaction-import[]
# end::read-write-transaction-import[]


def read_write_transaction_example(driver):
    with driver.session() as session:
        session.run("MATCH (_) DETACH DELETE _")

    # tag::read-write-transaction[]
    def create_person_node(tx, name):
        tx.run("CREATE (a:Person {name: $name})", name=name)

    def match_person_node(tx, name):
        result = tx.run(
            "MATCH (a:Person {name: $name}) RETURN count(a)", name=name
        )
        return result.single()[0]

    def add_person(name):
        with driver.session() as session:
            session.execute_write(create_person_node, name)
            return session.execute_read(match_person_node, name)

    # end::read-write-transaction[]

    result = add_person("Alice")
    result = add_person("Alice")

    with driver.session() as session:
        session.run("MATCH (_) DETACH DELETE _")

    return result


def test_example(driver):
    result = read_write_transaction_example(driver)
    assert result == 2
