from services.budget_service import BudgetService

def test_budget_logic():
    bs = BudgetService()
    
    # Setup
    category = "TestCategory"
    bs.set_budget(category, 100000)
    print(f"Initial Budget {category}: 100,000")
    
    # Test 1: Under Limit
    print("\nTest 1: Spend 50k (Under Limit)")
    deducted, excess = bs.deduct_budget(category, 50000)
    print(f"Result: Deducted={deducted}, Excess={excess}")
    assert deducted == 50000
    assert excess == 0
    
    current = bs.get_budgets().get(category.lower())
    print(f"Remaining Budget: {current}")
    assert current == 50000
    
    # Test 2: Overflow
    print("\nTest 2: Spend 70k (Overflow - 50k remaining)")
    deducted, excess = bs.deduct_budget(category, 70000)
    print(f"Result: Deducted={deducted}, Excess={excess}")
    assert deducted == 50000 # All remaining
    assert excess == 20000   # 70k - 50k
    
    current = bs.get_budgets().get(category.lower())
    print(f"Remaining Budget: {current}")
    assert current == 0
    
    # Test 3: Empty Budget
    print("\nTest 3: Spend 10k (Empty Budget)")
    deducted, excess = bs.deduct_budget(category, 10000)
    print(f"Result: Deducted={deducted}, Excess={excess}")
    assert deducted == 0
    assert excess == 10000
    
    # Cleanup
    bs.delete_budget(category)
    print("\n✅ Verification Passed!")

if __name__ == "__main__":
    test_budget_logic()
