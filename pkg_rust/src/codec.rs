// Copyright (c) "Neo4j"
// Neo4j Sweden AB [https://neo4j.com]
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

pub mod packstream;

use pyo3::prelude::*;

use crate::make_module_in_package;

pub(crate) fn register(m: &Bound<PyModule>) -> PyResult<()> {
    let mod_packstream = make_module_in_package(m, "packstream")?;
    packstream::register(&mod_packstream)?;
    m.add_submodule(&mod_packstream)?;

    Ok(())
}
