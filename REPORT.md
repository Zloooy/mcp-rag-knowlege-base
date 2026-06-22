# RAG Knowledge Base — MCP‑сервер с локальной LLM и LangGraph

## История проекта

Под каждый модуль создавался субагент со своей инструкцией и набором skills.
 * project-manager - без модуля и прав на запись, координация работы
 * mcp-coder - `src/mcp_server`, интерфейс mcp
 * data-engineer - `src/document_processing`, парсинг документов, разбивка на чанки
 * database-coder - `src/retrieval`, пробразование текста в эмбеддинги и индексы, сохранение и их извлечение из ChromaDB
 * llm-coder - `src/llm`, разработка адаптеров для взаимодействия с LLM
 * settings-coder - `src/core/settings.py` и `.env.example`, создание общего хранилища настроек, документирование переменных
 * graph-architect - `src/graph`, настройка LangGraph-графа
 * prompmt-engineer - `prompts/`, написание промптов для локальных LLM

 Каждый субагент с правами на запись также имел доступ к папке `tests`.
 После создания скелета проекта со всеми модулями, происходила отладка - сбор вопросов для датасета и создание тестового файла для `tests/test_retrieval.py`, включающего набор вопросов, которые должен был покрывать индекс. Исправлялся парсинг, чанки очищались от html-тегов и набора stopwords, подбирался оптимальный top_k, включающий все ответы.

## Технологии

| Компонент | Выбор | Обоснование |
|-----------|-------|-------------|
| Фреймворк сервера | FastMCP | Нативная поддержка MCP протокола, простое определение инструментов |
| Оркестрация | LangGraph StateGraph | Явное управление состоянием, условные переходы, циклы retry |
| Векторное хранилище | ChromaDB (in-process) | Не требует отдельного сервера, встроенные эмбеддинги |
| Ключевой поиск | rank-bm25 | Собственная реализация, полный контроль над ранжированием |
| Гибридный поиск | RRF (Reciprocal Rank Fusion) | Простая и эффективная мета-ранжирующая функция |
| LLM | Ollama (qwen2.5:3b) | Локальная работа без платных API |
| Парсинг кода | tree-sitter | AST-aware сплиттеры для .py/.js/.ts |

## Архитектурные решения

* Модульный парсинг. Для файлов с кодом чанки делились по включающим их сущностям - классам и функциям, не превышающим chunk_size. Для структурированных документов(json/yaml) чанк был объединён общим ключом, для Markdown - общим заголовком. Остальные файлы обрабатываются разбиением на чанки заданного размера.
* Модульное взаимодействие с LLM. Т. к. при тестировании использовались облачные провайдеры помимо ollama, для взаимодействия с LLM для автодополнения и для векторизации был создан общий интерфейс, позволяющий использовать OpenAI-compatible API.
* Скользящее окно top_k при расширении запроса RAG. На шаге broaden регулярно LLM попадались уже оценённые ранее чанки. Чтобы увеличить охват контекста, каждый n-ый вызов извлекает top_k * n чанков из которых выбирает k уникальных, не входивших в предыдущую выдачу, для оценки LLM
* Объединение чанков. Если в рамках одного запроса было возвращено несколько последовательных чанков из одного файла, LLM получает их вместе для оценки, чтобы расширить полезный контекст и уменьшить количество обращений.

## Пример удачного промпта для автономной доработки BM25-индекса

There is file @tests/test_retrieval.py . It is thought to optimize retrieval search, but the questions there contain too much additional information, they aren't real user questions. So, ask @database-coder to remove all additional information after question mark in every question. Then, let's try to optimize the whole pipeline to make the results more precise. Delegate tasks one-by-one to different specialists:
* @data-engineer is responsible for @src/document_processing , he can clear input files and rearrange chunks in them.
* @database-coder is responsible for retrieval - @src/retrieval folder.
* @graph-architect is responsible for @src/graph folder, he can change the whole pipeline if needed.
Remember, whole @tests/test_retrieval.py runs for about 4 minutes, so it would be better to run only part of test cases at one time.
I hope, it is possible to make the system find relevant documents in top_k=10, not top_k=25.
Don't give subagents parallel tasks to run tests - the loop should be run test -> test failed -> one or more subagents change the code -> run test again -> repeat if still fails.

В промпте обозначены функциональные требования к результату, инструменты (субагенты) и процесс работы с ними (agentic loop).

## Проблемы в ходе разработки

* @project-manager часто занимается микроменеджементом - диктует агентам дословный код, который нужно написать. Было улучшено расширением инструкции, но полностью устранить не удалось.
* Агенты часто пишут mock-код, содержащий заглушки вместо реальной логики. Исправляется добавлением конкретных требований к результату, тестов, также ревью кода через @project-manager.
* Несостыковка интерфейсов модулей. Для решения объекты, передаваемые между модулями, используют общие Pydantic-схемы. Также opencode запускает проверку типов при помощи pyright при каждой записи файла.
* Непрозрачный процесс оценки документов. Был исправлен созданием файла `tests/test_retrieval.py`, позволяющим тестировать индекс bm25 отдельно от LLM-эмбеддингов
* Долгий прогон тестов агентами. Решалось требованием прогонять конкретный тест и модуляризацией тестов для этого, ограничением по запуску теста только в конце задачи. Для ручного тестирования был создано хранилище хешей файлов, позволяющee повторно индексировать только изменившиеся файлы датасета.
