"""
Integration tests for the question generation pipeline.

Tests:
- End-to-end pipeline execution (with mocked LLM)
- Integration between modules
- Error handling across module boundaries
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from gum.clarification.question_engine import ClarifyingQuestionEngine
from gum.clarification.question_generator import QuestionGenerator
from gum.clarification.question_loader import load_flagged_propositions


class TestPipelineIntegration:
    """Integration tests for full pipeline."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        client = AsyncMock()
        
        # Mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "question": "Could you clarify what you meant by that?",
            "reasoning": "This proposition infers intent; clarifying confirms."
        })
        
        client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        return client
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = MagicMock()
        config.model = "gpt-4"
        return config
    
    @pytest.fixture
    def sample_flagged_file(self):
        """Create a sample flagged propositions file."""
        data = [
            {
                "prop_id": 1,
                "prop_text": "Arnav values communication with friends.",
                "triggered_factors": ["inferred_intent"],
                "observations": [
                    {"id": 451, "observation_text": "User messaged contacts"}
                ],
                "prop_reasoning": "Based on messaging"
            },
            {
                "prop_id": 2,
                "prop_text": "Arnav is focused on development.",
                "triggered_factors": ["ambiguity"],
                "observations": []
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(data, f)
            filepath = f.name
        
        yield filepath
        
        Path(filepath).unlink()
    
    @pytest.mark.asyncio
    async def test_end_to_end_pipeline(
        self, mock_openai_client, mock_config, sample_flagged_file
    ):
        """Test complete pipeline execution."""
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jsonl')
        output_path = output_file.name
        output_file.close()
        
        try:
            engine = ClarifyingQuestionEngine(
                openai_client=mock_openai_client,
                config=mock_config,
                input_source="file",
                input_file_path=sample_flagged_file,
                output_path=output_path
            )
            
            summary = await engine.run()
            
            # Check summary
            assert summary["total_processed"] == 2
            assert summary["successful"] >= 0
            assert "output_file" in summary
            
            # Check output file was created
            assert Path(output_path).exists()
            
            # Read and validate output
            with open(output_path, 'r') as f:
                lines = f.readlines()
                assert len(lines) > 0
                
                for line in lines:
                    result = json.loads(line)
                    assert "question" in result
                    assert "reasoning" in result
                    assert "factor" in result
                    assert "prop_id" in result
        
        finally:
            if Path(output_path).exists():
                Path(output_path).unlink()
    
    @pytest.mark.asyncio
    async def test_pipeline_with_filtering(
        self, mock_openai_client, mock_config, sample_flagged_file
    ):
        """Test pipeline with prop_ids and factor_ids filtering."""
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jsonl')
        output_path = output_file.name
        output_file.close()
        
        try:
            engine = ClarifyingQuestionEngine(
                openai_client=mock_openai_client,
                config=mock_config,
                input_source="file",
                input_file_path=sample_flagged_file,
                output_path=output_path
            )
            
            # Filter to only prop_id=1
            summary = await engine.run(prop_ids=[1])
            
            assert summary["total_processed"] == 1
        
        finally:
            if Path(output_path).exists():
                Path(output_path).unlink()


class TestGeneratorIntegration:
    """Integration tests for question generator."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        client = AsyncMock()
        
        # Mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "question": "Could you clarify what you meant by 'structured thinking'?",
            "reasoning": "The phrase is abstract; asking grounds the claim in specifics."
        })
        
        client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        return client
    
    @pytest.mark.asyncio
    async def test_generate_few_shot_question(self, mock_openai_client):
        """Test generating a few-shot question."""
        generator = QuestionGenerator(mock_openai_client, model="gpt-4")
        
        result = await generator.generate_question_pair(
            prop_id=1,
            prop_text="Arnav values communication with friends.",
            factor_id=3,  # Inferred Intent (few-shot)
            observations=[
                {"id": 451, "observation_text": "User messaged contacts"}
            ]
        )
        
        assert "question" in result
        assert "reasoning" in result
        assert "evidence" in result
        assert "factor" in result
        assert result["factor"] == "inferred_intent"
        assert result["prop_id"] == 1
    
    @pytest.mark.asyncio
    async def test_generate_controlled_qg_question(self, mock_openai_client):
        """Test generating a controlled QG question."""
        generator = QuestionGenerator(mock_openai_client, model="gpt-4")
        
        result = await generator.generate_question_pair(
            prop_id=2,
            prop_text="Arnav is an exceptional problem solver.",
            factor_id=1,  # Identity Mismatch (controlled QG)
            observations=[
                {"id": 100, "observation_text": "Solved complex challenge"}
            ]
        )
        
        assert "question" in result
        assert "reasoning" in result
        assert "evidence" in result
        assert result["factor"] == "identity_mismatch"
    
    @pytest.mark.asyncio
    async def test_generator_with_validation_retry(self, mock_openai_client):
        """Test generator retries on validation failure."""
        # First response invalid, second valid
        responses = [
            json.dumps({
                "question": "Why",  # Too short, invalid
                "reasoning": "Too brief"
            }),
            json.dumps({
                "question": "Could you clarify what you meant by that specific behavior?",
                "reasoning": "This asks for clarification on the observed behavior."
            })
        ]
        
        call_count = [0]
        
        async def mock_create(*args, **kwargs):
            response = MagicMock()
            response.choices = [MagicMock()]
            response.choices[0].message.content = responses[call_count[0]]
            call_count[0] += 1
            return response
        
        mock_openai_client.chat.completions.create = mock_create
        
        generator = QuestionGenerator(mock_openai_client, model="gpt-4")
        
        result = await generator.generate_question_pair(
            prop_id=1,
            prop_text="Test proposition",
            factor_id=1,  # Controlled QG with retry
            observations=[]
        )
        
        # Should succeed after retry
        assert "question" in result
        # Second (valid) response should be used
        assert len(result["question"]) > 10


class TestErrorHandling:
    """Test error handling across module boundaries."""
    
    @pytest.mark.asyncio
    async def test_generator_handles_api_errors(self):
        """Test that generator handles API errors gracefully."""
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )
        
        generator = QuestionGenerator(client, model="gpt-4")
        
        with pytest.raises(Exception):
            await generator.generate_question_pair(
                prop_id=1,
                prop_text="Test",
                factor_id=3,
                observations=[]
            )
    
    @pytest.mark.asyncio
    async def test_generator_handles_invalid_json(self):
        """Test that generator handles invalid JSON responses."""
        client = AsyncMock()
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "{ invalid json }"
        
        client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        generator = QuestionGenerator(client, model="gpt-4")
        
        with pytest.raises(ValueError, match="Failed to parse JSON"):
            await generator.generate_question_pair(
                prop_id=1,
                prop_text="Test",
                factor_id=3,
                observations=[]
            )
    
    @pytest.mark.asyncio
    async def test_pipeline_continues_on_individual_failures(
        self, mock_openai_client, mock_config
    ):
        """Test that pipeline continues even if some items fail."""
        # Create file with multiple props
        data = [
            {
                "prop_id": 1,
                "prop_text": "Prop 1",
                "triggered_factors": ["inferred_intent"],
                "observations": []
            },
            {
                "prop_id": 2,
                "prop_text": "Prop 2",
                "triggered_factors": ["opacity"],
                "observations": []
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(data, f)
            input_file = f.name
        
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jsonl')
        output_path = output_file.name
        output_file.close()
        
        try:
            # Mock client to fail on first call, succeed on second
            call_count = [0]
            
            async def mock_create(*args, **kwargs):
                if call_count[0] == 0:
                    call_count[0] += 1
                    raise Exception("API Error")
                else:
                    response = MagicMock()
                    response.choices = [MagicMock()]
                    response.choices[0].message.content = json.dumps({
                        "question": "Valid question?",
                        "reasoning": "Valid reasoning."
                    })
                    return response
            
            mock_openai_client.chat.completions.create = mock_create
            
            engine = ClarifyingQuestionEngine(
                openai_client=mock_openai_client,
                config=mock_config,
                input_source="file",
                input_file_path=input_file,
                output_path=output_path
            )
            
            summary = await engine.run()
            
            # Should have processed both, but one failed
            assert summary["total_processed"] == 2
            assert summary["failed"] >= 1
            assert summary["successful"] >= 1
        
        finally:
            Path(input_file).unlink()
            if Path(output_path).exists():
                Path(output_path).unlink()


class TestModuleIntegration:
    """Test integration between different modules."""
    
    @pytest.mark.asyncio
    async def test_loader_to_generator_data_flow(self):
        """Test that data flows correctly from loader to generator."""
        # Create sample file
        data = [
            {
                "prop_id": 1,
                "prop_text": "Test proposition",
                "triggered_factors": ["inferred_intent"],
                "observations": [{"id": 1, "observation_text": "Test obs"}]
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(data, f)
            filepath = f.name
        
        try:
            # Load propositions
            props = await load_flagged_propositions(source="file", file_path=filepath)
            
            assert len(props) == 1
            prop = props[0]
            
            # Verify data structure is compatible with generator
            assert "prop_id" in prop
            assert "prop_text" in prop
            assert "triggered_factors" in prop
            assert "observations" in prop
            
            # Verify factor names are valid
            from gum.clarification.question_config import get_factor_id_from_name
            for factor_name in prop["triggered_factors"]:
                factor_id = get_factor_id_from_name(factor_name)
                assert factor_id is not None
        
        finally:
            Path(filepath).unlink()
    
    def test_validator_compatible_with_generator_output(self):
        """Test that validator accepts generator output structure."""
        from gum.clarification.question_validator import QuestionValidator
        
        # Simulate generator output
        output = {
            "prop_id": 1,
            "factor": "inferred_intent",
            "question": "Could you clarify what you meant?",
            "reasoning": "This asks for clarification on intent.",
            "evidence": ["obs_1: test observation"]
        }
        
        validator = QuestionValidator()
        is_valid, errors = validator.validate_full_output(output)
        
        # Should be valid or have only minor warnings
        assert is_valid or len(errors) <= 1


class TestPropertyBasedIntegration:
    """Property-based integration tests."""
    
    @pytest.mark.asyncio
    async def test_pipeline_idempotency(self, mock_openai_client, mock_config):
        """Test that running pipeline twice produces consistent results."""
        data = [
            {
                "prop_id": 1,
                "prop_text": "Test",
                "triggered_factors": ["inferred_intent"],
                "observations": []
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(data, f)
            input_file = f.name
        
        output_file1 = tempfile.NamedTemporaryFile(delete=False, suffix='.jsonl')
        output_file2 = tempfile.NamedTemporaryFile(delete=False, suffix='.jsonl')
        output_path1 = output_file1.name
        output_path2 = output_file2.name
        output_file1.close()
        output_file2.close()
        
        try:
            # Run twice
            engine1 = ClarifyingQuestionEngine(
                openai_client=mock_openai_client,
                config=mock_config,
                input_source="file",
                input_file_path=input_file,
                output_path=output_path1
            )
            summary1 = await engine1.run()
            
            engine2 = ClarifyingQuestionEngine(
                openai_client=mock_openai_client,
                config=mock_config,
                input_source="file",
                input_file_path=input_file,
                output_path=output_path2
            )
            summary2 = await engine2.run()
            
            # Should have same counts (assuming deterministic mock)
            assert summary1["total_processed"] == summary2["total_processed"]
        
        finally:
            Path(input_file).unlink()
            if Path(output_path1).exists():
                Path(output_path1).unlink()
            if Path(output_path2).exists():
                Path(output_path2).unlink()

