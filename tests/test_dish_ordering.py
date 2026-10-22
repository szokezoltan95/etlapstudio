import unittest

from menu_core import insert_pending_dishes


class PendingDishInsertionTests(unittest.TestCase):
    def test_new_dish_is_inserted_before_its_daily_successor(self):
        global_order = list(range(1, 9)) + [99]
        daily_order = [1, 6, 99, 8]

        self.assertEqual(
            insert_pending_dishes(global_order, daily_order, {99}),
            [1, 2, 3, 4, 5, 6, 7, 99, 8],
        )

    def test_hidden_dishes_shift_without_changing_relative_order(self):
        global_order = [1, 2, 3, 4, 5, 6, 7, 99, 8, 100]
        daily_order = [2, 100, 3]

        self.assertEqual(
            insert_pending_dishes(global_order, daily_order, {100}),
            [1, 2, 100, 3, 4, 5, 6, 7, 99, 8],
        )

    def test_multiple_new_dishes_keep_their_daily_relative_order(self):
        global_order = [1, 2, 3, 4, 5, 6, 90, 91]
        daily_order = [2, 90, 91, 3]

        self.assertEqual(
            insert_pending_dishes(global_order, daily_order, {90, 91}),
            [1, 2, 90, 91, 3, 4, 5, 6],
        )

    def test_existing_daily_reorder_does_not_shuffle_global_defaults(self):
        global_order = [1, 2, 3, 4, 5]
        daily_order = [4, 1, 3]

        self.assertEqual(
            insert_pending_dishes(global_order, daily_order, set()),
            global_order,
        )


if __name__ == "__main__":
    unittest.main()
