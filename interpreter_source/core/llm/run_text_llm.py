"""
Text-based LLM runner for models without native function calling.

Parses markdown code blocks from the LLM response and yields them as executable code.
Supports multiple code blocks in a single response.
"""


def run_text_llm(llm, params):
    """
    Run LLM and parse markdown code blocks from the response.

    This is used for models that don't support native function/tool calling.
    The LLM outputs markdown code blocks which are parsed and executed.

    Improvements over original:
    - Supports multiple code blocks in a single response
    - Better handling of partial tokens
    - More robust language detection
    - Yields messages between code blocks
    """

    ## Setup
    if llm.execution_instructions:
        try:
            params["messages"][0]["content"] += "\n" + llm.execution_instructions
        except Exception:
            print('params["messages"][0]', params["messages"][0])
            raise

    ## State variables
    inside_code_block = False
    accumulated_block = ""
    language = None
    message_buffer = ""  # Buffer for non-code content
    code_block_count = 0

    # Track what we've already yielded to avoid duplicates
    last_yielded_content = ""

    for chunk in llm.completions(**params):
        if llm.interpreter.verbose:
            print("Chunk in run_text_llm:", chunk)

        if "choices" not in chunk or len(chunk["choices"]) == 0:
            continue

        content = chunk["choices"][0]["delta"].get("content", "")

        if content is None:
            continue

        accumulated_block += content

        # Wait if we might be in the middle of typing "```"
        # But don't wait if we already have a complete "```"
        if (accumulated_block.endswith("`") or accumulated_block.endswith("``")) and "```" not in accumulated_block:
            continue

        # Did we just enter a code block?
        if "```" in accumulated_block and not inside_code_block:
            # Yield any accumulated message content before the code block
            pre_code = accumulated_block.split("```")[0]
            if pre_code and pre_code != last_yielded_content:
                # Only yield new content
                new_content = pre_code[len(message_buffer):] if pre_code.startswith(message_buffer) else pre_code
                if new_content.strip():
                    yield {"type": "message", "content": new_content}
                    last_yielded_content = pre_code

            inside_code_block = True
            code_block_count += 1
            # Get everything after the opening ```
            accumulated_block = accumulated_block.split("```", 1)[1]
            language = None  # Reset language for new block
            message_buffer = ""  # Reset message buffer

        # Did we just exit a code block?
        if inside_code_block and "```" in accumulated_block:
            # Extract the code before the closing ```
            code_content = accumulated_block.split("```")[0]

            # Always strip the first line if it's a language identifier
            if "\n" in code_content:
                first_line = code_content.split("\n")[0].strip()
                # Check if first line is a language identifier (only letters)
                first_line_clean = "".join(char for char in first_line if char.isalpha()).lower()
                if first_line_clean and first_line_clean == first_line.strip().lower():
                    # First line is just a language identifier, strip it
                    if language is None:
                        language = first_line_clean or "python"
                    code_content = "\n".join(code_content.split("\n")[1:])
                elif not first_line:
                    # Empty first line, strip it
                    if language is None:
                        language = "python" if not llm.interpreter.os else "text"
                    code_content = "\n".join(code_content.split("\n")[1:])

            # Yield the final code content
            if code_content.strip():
                yield {
                    "type": "code",
                    "format": language or "python",
                    "content": code_content,
                }

            # Reset state for potential next code block
            inside_code_block = False
            # Keep content after the closing ``` for potential next block or message
            remaining = "```".join(accumulated_block.split("```")[1:])
            accumulated_block = remaining
            language = None

            # If there's content after the code block, continue processing
            # This allows handling multiple code blocks
            if remaining.strip():
                message_buffer = ""
                continue
            else:
                # No more content, we're done with this response
                # But don't return - there might be more chunks coming
                continue

        # If we're in a code block, handle language detection and content yielding
        if inside_code_block:
            if language is None and "\n" in accumulated_block:
                # First line should be the language
                first_line = accumulated_block.split("\n")[0].strip()

                if first_line == "":
                    # No language specified, default based on mode
                    language = "python" if not llm.interpreter.os else "text"
                else:
                    # Clean language identifier (remove non-alpha chars)
                    language = "".join(char for char in first_line if char.isalpha()).lower()
                    if not language:
                        language = "python"

                # Yield the language line has been processed
                if llm.interpreter.verbose:
                    print(f"Detected language: {language}")

            # If we have a language, yield code content
            if language:
                # Calculate what's new since last yield
                # Skip the language line in the content
                if "\n" in accumulated_block:
                    code_portion = "\n".join(accumulated_block.split("\n")[1:])
                else:
                    code_portion = ""

                # Only yield the new content from this chunk
                # Make sure we don't include closing ``` in the content
                if content and language not in content:
                    # Strip closing backticks if present
                    clean_content = content
                    if "```" in clean_content:
                        clean_content = clean_content.split("```")[0]
                    if clean_content:
                        yield {
                            "type": "code",
                            "format": language,
                            "content": clean_content,
                        }

        # If we're not in a code block, buffer message content
        elif not inside_code_block:
            # Yield message content as it comes
            if content:
                yield {"type": "message", "content": content}
                message_buffer += content

    # Handle any remaining content after stream ends
    if inside_code_block and accumulated_block.strip():
        # Stream ended while in a code block (incomplete)
        # Still yield what we have
        if language:
            remaining_code = "\n".join(accumulated_block.split("\n")[1:]) if "\n" in accumulated_block else accumulated_block
            if remaining_code.strip():
                yield {
                    "type": "code",
                    "format": language,
                    "content": remaining_code,
                }
