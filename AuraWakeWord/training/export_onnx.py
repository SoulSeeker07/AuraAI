import argparse
import sys
from pathlib import Path

# Fix for UnicodeEncodeError on Windows during torch.onnx.export
sys.stdout.reconfigure(encoding='utf-8')

import torch
from train_model import AuraWakeModel, NUM_SAMPLES, N_MELS

def export_to_onnx(model_path: Path, output_path: Path):
    print(f"Loading PyTorch model from {model_path}...")
    
    device = torch.device("cpu")
    model = AuraWakeModel().to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    
    # Create dummy input that matches the model's expected input shape
    # The input to our CNN is the log mel spectrogram:
    # (batch_size, channels, n_mels, time_steps)
    # The time_steps for 2.0s audio at 16kHz with hop_length=160 is (32000 // 160) + 1 = 201
    
    dummy_time_steps = (NUM_SAMPLES // 160) + 1
    dummy_input = torch.randn(1, 1, N_MELS, dummy_time_steps, device=device)
    
    print(f"Exporting ONNX model to {output_path}...")
    
    torch.onnx.export(
        model,                      # model being run
        dummy_input,                # model input (or a tuple for multiple inputs)
        str(output_path),           # where to save the model
        export_params=True,         # store the trained parameter weights inside the model file
        opset_version=18,           # the ONNX version to export the model to
        do_constant_folding=True,   # whether to execute constant folding for optimization
        input_names=['input'],      # the model's input names
        output_names=['output'],    # the model's output names
        dynamic_axes={'input': {0: 'batch_size'},    # variable length axes
                      'output': {0: 'batch_size'}}
    )
    
    print("Export complete!")
    
    # Verify the exported model
    import onnx
    onnx_model = onnx.load(str(output_path))
    onnx.checker.check_model(onnx_model)
    print("ONNX model structural verification successful.")
    
    # Verify outputs
    import onnxruntime as ort
    import numpy as np
    
    print("Verifying PyTorch vs ONNX outputs...")
    pytorch_out = model(dummy_input).detach().numpy()
    
    ort_session = ort.InferenceSession(str(output_path), providers=['CPUExecutionProvider'])
    ort_inputs = {ort_session.get_inputs()[0].name: dummy_input.numpy()}
    onnx_out = ort_session.run(None, ort_inputs)[0]
    
    np.testing.assert_allclose(pytorch_out, onnx_out, rtol=1e-03, atol=1e-05)
    print("SUCCESS: ONNX and PyTorch output scores match exactly!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export AuraWakeWord Model to ONNX")
    parser.add_argument("--input", type=str, default="aura_model_best.pt", help="PyTorch model filename in models/")
    parser.add_argument("--output", type=str, default="aura_wakeword.onnx", help="Output ONNX filename in models/")
    args = parser.parse_args()
    
    base_dir = Path(__file__).resolve().parent.parent
    models_dir = base_dir / "models"
    
    input_path = models_dir / args.input
    output_path = models_dir / args.output
    
    if not input_path.exists():
        print(f"Error: Input model not found at {input_path}")
        exit(1)
        
    export_to_onnx(input_path, output_path)
