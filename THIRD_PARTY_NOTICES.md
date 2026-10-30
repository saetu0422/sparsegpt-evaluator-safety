# Third-party provenance and license boundaries

## HarmBench classifier template

`code/HB_standard_template.txt` and the byte-identical continuation copy `experiments/2026-10-30_intermediate159/HB_standard_template.txt` are derived from `LLAMA2_CLS_PROMPT["prompt"]` in [centerforaisafety/HarmBench — eval_utils.py](https://github.com/centerforaisafety/HarmBench/blob/main/eval_utils.py), inspected 2026-10-29. The upstream file's Git blob SHA at inspection was `be95edd9523de0cde2a7823217b26983d57c496b` (a file blob identifier, **not a repository commit**).

Copyright (c) 2024 centerforaisafety. The upstream [MIT license](https://github.com/centerforaisafety/HarmBench/blob/main/LICENSE) is retained in `third_party/HarmBench-LICENSE.txt`.

The experiment removed the blank line before `---` and the blank line before `Answer:`; all other template content matches the inspected upstream string. Experimental template SHA-256: `6e40c2f76a74aa2dc38d83b557220017311e29c249d938a256c3f0a2d87f0cac`. The upstream extracted prompt string had SHA-256 `788f4f6aa1491c433c4da76c9140cfc30966cea3ff3875c4d0fcb336d92f60e0`. Packaging retains the experimental bytes without changing the completed protocol.

The strict HB yes/no parser follows the upstream classifier rule; the project's invalid/abstain separation and storage logic are additional implementation choices. The complete upstream `eval_utils.py` is not vendored.

## Models, methods and data

- [SparseGPT](https://github.com/IST-DASLab/sparsegpt) supplies the research-method context; its implementation and pruned weights are not vendored here.
- [HarmBench](https://github.com/centerforaisafety/HarmBench) supplies benchmark/evaluator context. Raw benchmark prompts, contextual material, book/lyric text and copyright hash references are not redistributed here.
- [HarmBench-Llama-2-13b-cls](https://huggingface.co/cais/HarmBench-Llama-2-13b-cls) and [Llama-Guard-3-8B](https://huggingface.co/meta-llama/Llama-Guard-3-8B) are externally obtained evaluator dependencies. Exact revisions are recorded in the scientific provenance. No model weights, tokenizer files or credentials are bundled.
- The Llama Guard model card identifies Llama 3.1 license terms. Consult each upstream model's applicable license, acceptable-use terms and access conditions; this repository does not grant rights to those models.
- Python, NumPy, PyTorch, Transformers and Accelerate are external dependencies, not vendored software. Their terms remain separate.

## Project license status

No repository-wide license is assigned by this publication. The HarmBench MIT notice applies to the identified upstream-derived material, not automatically to unrelated project code or data. An open-source license for the project's own code requires a separate owner decision. Public visibility alone is not a license grant.
