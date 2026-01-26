import torch
from torch_geometric.data import Data

# [수정] weights_only=False 옵션 추가 (PyTorch 2.6 이상 필수)
# 경로도 에러 메시지에 나온 실제 파일명으로 맞췄습니다.
file_path = '../output/AES_T500_TjIn_util0.7_clk2.0_top.netlist.pt'

try:
    # ★ 여기가 핵심 수정 포인트입니다 ★
    data = torch.load(file_path, weights_only=False)

    print("=== 데이터 뜯어보기 ===")
    print(f"1. 전체 구조: {data}")
    print(f"\n2. 노드(게이트) 개수: {data.num_nodes}")
    
    # x(피처)가 있는지 확인하고 출력
    if hasattr(data, 'x') and data.x is not None:
        print(f"3. 노드 특징(Feature) 크기: {data.x.shape}")
    else:
        print("3. 노드 특징(Feature): 없음 (One-hot encoding 확인 필요)")

    print(f"4. 엣지(연결선) 개수: {data.num_edges}")
    if hasattr(data, 'y_trojan'):
        trojan_count = data.y_trojan.sum().item()
        print(f"▶ 발견된 트로이 게이트 개수: {trojan_count} 개")
    
        if trojan_count > 0:
            print("✅ 성공! 파서가 트로이 게이트를 제대로 인식했습니다.")
        else:
            print("❌ 실패! 이름(Trojan_n8)은 있는데, 파서가 이걸 1로 표시하지 않고 0으로 무시했습니다.")
    else:
        print("❓ y_trojan 속성 자체가 없습니다.")
    
    # y(정답)가 있는지 확인하고 출력
    if hasattr(data, 'y') and data.y is not None:
        print(f"5. 정답(Label) 크기: {data.y.shape}")
        
        # y_func나 func_mask 등 다른 이름으로 저장되었을 수도 있으므로 확인
        trojan_count = data.y.sum().item()
        print(f"\n6. 트로이 게이트 개수: {trojan_count}")
        
        if trojan_count == 0:
            print("   (주의: 트로이 게이트가 0개입니다. 라벨링 로직 점검이 필요할 수 있습니다.)")
    else:
        print("5. 정답(Label): y 속성이 없습니다. (data.y_func 등을 확인해보세요)")
        # 혹시 y 대신 y_func로 저장되었는지 확인
        if hasattr(data, 'y_func'):
             print(f"   -> 대신 'y_func'가 있습니다: {data.y_func.shape}")

except FileNotFoundError:
    print(f"오류: 파일을 찾을 수 없습니다. 경로를 확인해주세요: {file_path}")
except Exception as e:
    print(f"오류 발생: {e}")