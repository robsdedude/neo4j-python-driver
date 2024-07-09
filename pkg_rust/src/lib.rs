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

pub mod codec;

use pyo3::prelude::*;

/// A Python module implemented in Rust.
#[pymodule]
#[pyo3(name = "_rust")]
fn packstream(m: &Bound<PyModule>) -> PyResult<()> {
    let mod_codec = make_module_in_package(m, "codec")?;
    codec::register(&mod_codec)?;
    m.add_submodule(&mod_codec)?;

    Ok(())
}

fn make_module_in_package<'py>(
    parent_module: &Bound<'py, PyModule>,
    submodule_name: &str,
) -> PyResult<Bound<'py, PyModule>> {
    let py = parent_module.py();

    let submodule = PyModule::new_bound(py, submodule_name)?;
    let full_name = format!("{}.{}", parent_module.name()?, submodule_name);
    parent_module.add_submodule(&submodule)?;

    // hack to make python pick up the submodule as a package
    // https://github.com/PyO3/pyo3/issues/1517#issuecomment-808664021
    submodule.setattr("__name__", &full_name)?;
    py.import_bound("sys")?
        .getattr("modules")?
        .set_item(&full_name, &submodule)?;

    Ok(submodule)
}
