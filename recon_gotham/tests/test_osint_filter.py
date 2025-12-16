
import unittest
from recon_gotham.core.asset_graph import AssetGraph

class TestOSINTFilter(unittest.TestCase):
    def setUp(self):
        self.graph = AssetGraph()
        self.target = "tahiti-infos.com"

    def test_filter_org_generic(self):
        # Should be blocked
        res = self.graph.add_org("Target Corporation", target_domain=self.target)
        self.assertIsNone(res, "Generic 'Target Corporation' should be blocked")

        res2 = self.graph.add_org("Example Org", target_domain=self.target)
        self.assertIsNone(res2, "Generic 'Example Org' should be blocked (via fuzzy matching logic)")

    def test_filter_org_valid(self):
        # Should be accepted
        res = self.graph.add_org("Tahiti-Infos Media", target_domain=self.target)
        self.assertIsNotNone(res)
        self.assertTrue(res.startswith("org:"))

    def test_filter_saas(self):
        # SaaS names don't need to match target, but must not be forbidden generic strings
        res = self.graph.add_saas_app("Microsoft 365", target_domain=self.target)
        self.assertIsNotNone(res)
        
        # Generic forbidden check
        res2 = self.graph.add_saas_app("Target Corporation", target_domain=self.target)
        self.assertIsNone(res2)

    def test_filter_repo(self):
        # Repos must match target
        res = self.graph.add_repository("https://github.com/tahiti-infos/app", target_domain=self.target)
        self.assertIsNotNone(res)

        res2 = self.graph.add_repository("https://github.com/generic/repo", target_domain=self.target)
        self.assertIsNone(res2, "Unrelated repo should be blocked")

if __name__ == '__main__':
    unittest.main()
