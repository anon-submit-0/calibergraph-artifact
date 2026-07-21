from typing import List, Tuple, Dict, Optional
from collections import defaultdict
import sqlite3
import pandas as pd

INF = 1000000

class PrimaryForeignKeyPair(object):
    def __init__(self, primary_table: str, foreign_table: str) -> None:
        self._primary_table = primary_table
        self._foreign_table = foreign_table
        self._constrains: List[Tuple[str, str]] = []

    def add_constrain(self, constrain_p: str, constrain_f: str) -> bool:
        if (constrain_p, constrain_f) in self._constrains:
            return False
        self._constrains.append((constrain_p, constrain_f))
        return True

    @property
    def constrains(self) -> List[Tuple[str, str]]:
        return self._constrains

    @property
    def primary_table(self) -> str:
        return self._primary_table

    @property
    def foreign_table(self) -> str:
        return self._foreign_table

    def to_dict(self) -> dict:
        if len(self._constrains) == 1:
            return {"eq": [f"{self._primary_table}.{self._constrains[0][0]}", f"{self._foreign_table}.{self._constrains[0][1]}"]}
        elif len(self._constrains) > 1:
            return {"and": [{"eq": [f"{self._primary_table}.{constrain[0]}", f"{self._foreign_table}.{constrain[1]}"]} for constrain in self._constrains]}
        raise ValueError("Empty Primary-Foreign Key Pair.")
    
    def __str__(self) -> str:
        return str(self.constrains)

    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, PrimaryForeignKeyPair):
            return False
        if self.primary_table != __value.primary_table or self.foreign_table != __value.foreign_table:
            return False
        if len(self.constrains) != len(__value.constrains):
            return False
        self.constrains.sort()
        __value.constrains.sort()
        if self._constrains != __value.constrains:
            return False
        return True

Node = str
Edge = List[PrimaryForeignKeyPair]

class Graph(object):
    def __init__(self) -> None:
        self.nodes: List[Node] = []
        self.edges: Dict[Node, Dict[Node, Optional[Edge]]] = defaultdict(lambda: defaultdict(lambda: None))

    def __getstate__(self) -> object:
        return {
            "nodes": self.nodes,
            "edges": {k: {vk: vv for vk, vv in v.items()} for k, v in self.edges.items()}
        }

    def __setstate__(self, state):
        self.nodes = state["nodes"]
        self.edges = defaultdict(lambda: defaultdict(lambda: None))
        for k, v in self.edges.items():
            for vk, vv in v.items():
                self.edges[k][vk] == vv

    def __getitem__(self, key: Node) -> Dict[Node, Optional[Edge]]:
        return self.edges[key]

    def add_node(self, name: str) -> bool:
        if name in self.nodes:
            return False
        self.nodes.append(name)
        return True

    def add_edge(self, tail: Node, head: Node, value: PrimaryForeignKeyPair) -> bool:
        if tail not in self.nodes or head not in self.nodes:
            return False
        if self.edges[tail][head] is None:
            self.edges[tail][head] = []
        self.edges[tail][head].append(value)
        return True

    def __str__(self) -> str:
        s = f"Nodes: {self.nodes}\n"
        s += "Edges:\n"
        strs = []
        for i in self.nodes:
            for j in self.nodes:
                if self.edges[i][j] is not None:
                    strs.append(f"{i} -> {j} | " + ", ".join([str(x) for x in self.edges[i][j]]))
        s += "\n".join(strs)
        return s

def floyd(nodes, edges):
    shortest_paths = defaultdict(lambda: defaultdict(lambda: None))
    if nodes is None or edges is None:
        return shortest_paths
    for node in nodes:
        shortest_paths[node][node] = [node]
    for i in nodes:
        for j in nodes:
            if edges[i][j] is not None:
                shortest_paths[i][j] = [i, edges[i][j], j]
            elif edges[j][i] is not None:
                shortest_paths[i][j] = [i, edges[j][i], j]

    dis = defaultdict(lambda: defaultdict(int))
    for i in nodes:
        for j in nodes:
            if shortest_paths[i][j] is not None:
                dis[i][j] = (len(shortest_paths[i][j]) - 1) / 2
            else:
                dis[i][j] = INF

    for k in nodes:
        for i in nodes:
            for j in nodes:
                if dis[i][k] + dis[k][j] < dis[i][j]:
                    dis[i][j] = dis[i][k] + dis[k][j]
                    shortest_paths[i][j] = shortest_paths[i][k][:-1] + shortest_paths[k][j]
    return shortest_paths

def steiner_tree(graph: Graph, nodes: List[Node], edges: Optional[Dict[Node, Dict[Node, Optional[Edge]]]]=None) -> List[Tuple[List[Node], List[Edge]]]:
    subtrees: List[Tuple[List[Node], List[Edge]]] = []
    if len(nodes) == 0:
        subtrees = [[], []]
    for node in nodes:
        subtrees.append([[node], []])
    flag = False
    shortest_paths = floyd(nodes=nodes, edges=edges)
    for _ in range(len(nodes)):
        num_subtrees = len(subtrees)
        if num_subtrees == 1:
            break
        min_len = INF
        min_i = None
        min_j = None
        min_tail = None
        min_head = None
        for i in range(num_subtrees):
            for j in range(i + 1, num_subtrees):
                for i_node in subtrees[i][0]:
                    for j_node in subtrees[j][0]:
                        if shortest_paths[i_node][j_node] is None:
                            continue
                        if (len(shortest_paths[i_node][j_node]) - 1) / 2 < min_len:
                            min_len = (len(shortest_paths[i_node][j_node]) - 1) / 2
                            min_i = i
                            min_j = j
                            min_tail = i_node
                            min_head = j_node
        if min_i is None or min_j is None:
            if flag:
                break
            flag = True
            shortest_paths = floyd(graph.nodes, graph.edges)
            continue

        min_path = shortest_paths[min_tail][min_head]
        subtrees[min_i][0] = list(dict.fromkeys(subtrees[min_i][0] + [min_path[i] for i in range(0, len(min_path), 2)] + subtrees[min_j][0]))
        subtrees[min_i][1] += [min_path[i] for i in range(1, len(min_path) - 1, 2)] + subtrees[min_j][1]
        subtrees.pop(min_j)
    return subtrees

def execute_query(database, query):
    connection = sqlite3.connect(database)
    cursor = connection.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    dict_results = []
    for r in results:
        dict_results.append({c: v for c, v in zip(columns, r)})
    cursor.close()
    connection.close()
    return dict_results

class DatabaseAnalyzer(object):
    def __init__(self, database: str) -> None:
        self.database = database
        self.extend_relationships()

    @property
    def tables(self) -> List[str]:
        if not hasattr(self, "_tables"):
            self._tables = [x["name"].lower() for x in execute_query(self.database, "SELECT name FROM sqlite_master WHERE type = 'table'")]
        return self._tables

    def analyze_columns(self) -> None:
        if not hasattr(self, "_columns"):
            self._columns = {}
            for table in self.tables:
                table_name = f"`{table}`"
                self._columns[table] = execute_query(self.database, f"PRAGMA table_info({table_name})")

    @property
    def columns(self) -> Dict[str, List[str]]:
        if not hasattr(self, "_column_names"):
            self.analyze_columns()
            self._column_names = {}
            for table in self.tables:
                self._column_names[table] = [x["name"].lower() for x in self._columns[table]]
        return self._column_names

    @property
    def primary_keys(self) -> Dict[str, List[str]]:
        if not hasattr(self, "_primary_keys"):
            self.analyze_columns()
            self._primary_keys = defaultdict(list)
            for table in self.tables:
                for column in self._columns[table]:
                    if column["pk"] != 0:
                        self._primary_keys[table].append(column["name"].lower())
                if len(self._primary_keys[table]) == 0:
                    for column in self._columns[table]:
                        if column["name"].lower() == "id" or column["name"].lower() == table + "_id":
                            self._primary_keys[table].append(column["name"].lower())
        return self._primary_keys

    @property
    def types(self) -> Dict[str, Dict[str, str]]:
        if not hasattr(self, "_column_types"):
            self.analyze_columns()
            self._column_types = defaultdict(dict)
            for table in self.tables:
                for column in self._columns[table]:
                    self._column_types[table][column["name"].lower()] = column["type"]
        return self._column_types

    @property
    def foreign_keys(self) -> Dict[str, Dict[str, str]]:
        if not hasattr(self, "_foreign_keys"):
            self._foreign_keys = defaultdict(dict)
            for table in self.tables:
                table_name = f"`{table}`"
                keys = execute_query(self.database, f"PRAGMA foreign_key_list({table_name})")
                for key in keys:
                    if key["to"] is None or key["from"] is None or key["table"] is None:
                        continue
                    self._foreign_keys[table][key["from"].lower()] = key["table"].lower() + '.' + key["to"].lower()
        return self._foreign_keys

    @property
    def primary_foreign_keys(self) -> Graph:
        if not hasattr(self, "_pf_keys"):
            self._pf_keys = Graph()
            for table in self.tables:
                self._pf_keys.add_node(table)
            for table in self.tables:
                table_name = f"`{table}`"
                pf_keys = execute_query(self.database, f"PRAGMA foreign_key_list({table_name})")
                if len(pf_keys) == 0:
                    continue
                i = 0
                keypair = PrimaryForeignKeyPair(pf_keys[0]["table"].lower(), table)
                for pf_key in pf_keys:
                    if pf_key["to"] is None or pf_key["from"] is None or pf_key["table"] is None:
                        continue
                    if pf_key["id"] != i:
                        i = pf_key["id"]
                        self._pf_keys.add_edge(keypair.primary_table, table, keypair)
                        keypair = PrimaryForeignKeyPair(pf_key["table"].lower(), table)
                    keypair.add_constrain(pf_key["to"].lower(), pf_key["from"].lower())
                self._pf_keys.add_edge(keypair.primary_table, table, keypair)
        return self._pf_keys

    def extend_relationships(self) -> None:
        num_tables = len(self.tables)
        for i in range(num_tables - 1):
            itable = self.tables[i]
            for j in range(i + 1, num_tables):
                jtable = self.tables[j]
                for icolumn in self.columns[itable]:
                    for jcolumn in self.columns[jtable]:
                        if len(icolumn) == 1 or len(jcolumn) == 1:
                            continue # 单词长度太小
                        if jtable in self.primary_foreign_keys[itable] or itable in self.primary_foreign_keys[jtable]:
                            if icolumn in self.foreign_keys[itable] or jcolumn in self.foreign_keys[jtable]:
                                continue # 是外键
                        if self.types[itable][icolumn] != self.types[jtable][jcolumn]:
                            continue # 类型不一致
                        if len(self.primary_keys[itable]) == 1 and icolumn in self.primary_keys[itable] and len(self.primary_keys[jtable]) == 1 and jcolumn in self.primary_keys[jtable]:
                            continue # 都是主键
                        li = icolumn
                        lj = jcolumn
                        if li == "id":
                            li = itable + "_" + li
                        if lj == "id":
                            lj = jtable + "_" + lj
                        if li != lj:
                            if li.find(lj) == -1 and lj.find(li) == -1:
                                continue # 从单词级别来看, 两个列指代不类似

                        from_table = None
                        if icolumn in self.primary_keys[itable]:
                            from_table = itable
                        elif jcolumn in self.primary_keys[jtable]:
                            from_table = jtable
                        else:
                            continue # 其中至少有一个是主键

                        f, t = itable, jtable
                        fc, tc = icolumn, jcolumn
                        if from_table == jtable:
                            f, t = jtable, itable
                            fc, tc = jcolumn, icolumn
                        if floyd(self.primary_foreign_keys.nodes, self.primary_foreign_keys.edges)[t][f] is not None and "id" not in li and "id" not in lj:
                            continue
                        fk = PrimaryForeignKeyPair(f, t)
                        fk.add_constrain(fc, tc)
                        self.primary_foreign_keys.add_edge(f, t, fk)
