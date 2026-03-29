"""
简单的集成测试示例
"""
import asyncio
import json
import sys

# 加入项目路径
sys.path.insert(0, '.')

from models import UserMenuConstraints, IngredientItem
from agent import node_1_planning_extract, node_2_concurrent_retrieval, node_3_generate_meal_plan_stream


async def test_workflow():
    """测试完整工作流"""
    
    print("=" * 60)
    print("🧪 美食排菜 Agent 工作流测试")
    print("=" * 60)
    
    # 模拟用户输入
    user_input = """
    我家里有：5个土豆、250克五花肉、3个番茄、半斤豆角。
    今晚4个人吃饭，想做2菜1汤。
    我不吃辣，想要清淡的口味。
    """
    
    print(f"\n📝 用户输入:\n{user_input}\n")
    
    try:
        # ===== Node 1: 规划提取 =====
        print("\n[Node 1] 规划提取...")
        print("-" * 60)
        
        constraints = await node_1_planning_extract(user_input)
        
        print(f"✅ 提取成功！")
        print(f"📦 食材清单:")
        for ing in constraints.available_ingredients:
            print(f"  - {ing.name}: {ing.quantity}")
        
        print(f"\n🚫 忌口:")
        for allergy in constraints.allergies_and_dislikes:
            print(f"  - {allergy}")
        
        print(f"\n👥 就餐人数: {constraints.portion_size}")
        print(f"🎯 全局需求: {constraints.global_requests}")
        
        print(f"\n🔍 生成的搜索词:")
        for i, query in enumerate(constraints.search_queries, 1):
            print(f"  {i}. {query}")
        
        # ===== Node 2: 并发检索 (演示，不实际执行网络请求) =====
        print("\n\n[Node 2] 并发检索...")
        print("-" * 60)
        print("⏭️  演示模式：跳过实际网络请求")
        print("✅ 检索阶段演示完成")
        
        # ===== Node 3: 菜谱生成 (演示) =====
        print("\n\n[Node 3] 菜谱生成...")
        print("-" * 60)
        print("⏭️  演示模式：流式生成菜谱\n")
        
        print("=" * 60)
        print("✨ 工作流测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_workflow())
