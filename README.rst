****************************
Neo4j Bolt Driver for Python
****************************
.. FIXME: tmp!

This is an API preview for vector types.

Quick overview of the suggested API:

.. code-block:: python

    from neo4j import Vector

    # Create a vector (raw big-endian byte buffer by default)
    v = Vector("i16", b"\x00\x01\x02\x03")
    # or (less performant, but much more user-friendly)
    v = Vector.from_native("i16", [1, 513])

    # Get a vector
    v = driver.execute_query(
        "MATCH (d:Doc) RETURN d.embedding AS v LIMIT 1",
        database_="neo4j",
        # only for this preview build
        auto_transform_vec_=True,
    ).records[0]["v"]
    # Working with the vector
    print(f"Got vector of type {v.dtype} with {len(v)} elements: {v}")
    print("raw bytes:", v.raw())
    print("python list:", v.to_native())
    print("as numpy array:", v.to_numpy())

There are some more methods to convert from and to Vectors.
Check the `Docs <built_docs/types/vector.html>`_ for more information
(you might have to download the docs folder and open the html file locally).

The docs above mention the rust extensions at some point.
That does not yet work in this preview as no matching rust extensions is publicly available yet.

.. admonition:: note

    Vector types are not yet supported on a protocol layer. This means that the driver cannot send or receive vectors
    from the DBMS.
    To still be able to play with the vector types, this preview

    * will send every vector as a list of native types (e.g. ``int`` or ``float``) to the DBMS
    * has a temporary configuration option for sessions and `driver.execute_query` called `auto_transform_vec`.
      When set to `True`, the driver will automatically transform all homogeneous int and float lists into ``i64`` and
      ``f64`` vectors respectively.

    Note that neither will be present in the final version. Vectors will be their completely own type and the driver
    will not automatically convert them to or from lists.

Example
-------

.. code-block:: python

    from neo4j import (
        GraphDatabase,
        Vector,
    )

    URL = "neo4j://localhost:7687"
    AUTH = ("neo4j", "password")

    with GraphDatabase.driver(URL, auth=AUTH) as driver:
        doc = driver.execute_query(
            """
            MERGE (d:Document {id: 1, title: "Hello World", embedding: $embedding})
            RETURN d
            """,
            database_="neo4j",
            result_transformer_=lambda res: res.single(strict=True),
            auto_transform_vec_=True,
            embedding=Vector.from_native("f64", [0.1, 0.2, 0.3, 0.4]),
        )
        vec = doc["d"]["embedding"]
        print(vec)

Installation
------------
.. code-block:: bash

    pip install "neo4j[numpy,pyarrow] @ git+https://github.com/robsdedude/neo4j-python-driver.git@vector-types-preview1"
