import re
import Joins
from TableModule import Table
from arguments import db_runtime_context

class select_argument(object):
    def __init__(self, queryInput):
        self.queryInput = " ".join(queryInput)

    #currently only supports pulling the data
    def execute(self):
        global db_runtime_context
        '''
        Purpose:    Implementation of the SELECT statement.  
        Parameters: None
        Returns: None
        '''

        fields, aliases, conditions, joinType = self.__parseTables()
        


        conditionColumn = None
        conditionValue = None
        conditionOperator = None
        if conditions is not None:
            conditions = list(filter(None, re.split(r"(=|!=|<>|<|>|<=|>=)", conditions)))
            conditionColumn = conditions[0].strip()
            conditionOperator = conditions[1].strip()
            conditionValue = conditions[2].strip()

        columnInTables = False
        # For each table/column pair verify add the Table objects to a list.
        for table in fields.keys():
            temp = db_runtime_context.current_db.getTableByName(table)
            if temp is None:
                print ("!Failed to query table", table, "because it does not exist.")
                return None
            if "*" not in fields[table]:
                for column in fields[table]:
                    if not temp.attrExists(column):
                        print ("!Failed to query table", table, "because column",column,"does not exist.")
                        return None
        
        # Step One: Replace aliases in conditions with table names
        conditions = self.__replaceAliasesInConditional(conditions, aliases)


        tableName1, columns1, tableName2, columns2 = None, None, None, None
        if conditions is not None:
            tableName1, columns1 = self.__splitColAndTable(conditions[0])
            tableName2, columns2 = self.__splitColAndTable(conditions[2])


            if tableName1 is not None and tableName1 not in list(fields.keys()):
                print ("!Failed to query because", tableName1, "is not being selected.")
                return None


            if tableName2 is not None and tableName2 not in list(fields.keys()):
                print ("!Failed to query because", tableName2, "is not being selected.")
                return None

        #working table is the table that is a copy of the table that is selected and will be printed out when the
        #provided schemas and conditions are parsed out
        workingTable = Table(None, "MERGE", True)

        #Here we will parse out the attributes that will be printed out by pulling the specified table from the database
        tables = []
        attrList = [] 
        schema = {}
        for tableName, attrs in list(fields.items()):
            tmp = db_runtime_context.current_db.getTableByName(tableName)

            tname = tmp.getFriendlyName()

            attrList += [tname + "." + attr for attr in attrs]
            tables.append(tmp)

            #Here we create a modified schema that is based off what is requested and will be used to form what 
            #is returned for in the working tbale
            modifiedSchema = {}
            for k, v in list(tmp.schema.items()):
                modifiedSchema[tname + "." + k] = v 
            schema = {**schema, **modifiedSchema}

        if len(tables) == 1:
            workingTable = tables[0]
            attrList = fields[workingTable.getFriendlyName()]
            if conditions is not None:
                conditions[0] = columns1 
                conditions[2] = columns2 
        elif joinType == Joins.INNER_JOIN:
            tname1 = tables[0].getFriendlyName()
            tname2 = tables[1].getFriendlyName()
            for tb1Row in tables[0].getDataByAttrName("*"):
                tb1Row = self.__addTableNameToRow(tname1, tb1Row) 
                for tb2Row in tables[1].getDataByAttrName("*"):
                    tb2Row = self.__addTableNameToRow(tname2, tb2Row)
                    row = {**tb1Row, **tb2Row}
                    workingTable.rows.append(row)
            workingTable.setSchema(schema)
        else:
            workingTable = Table.OuterJoin(tables[0], tables[1], joinType, conditions)
            workingTable.setSchema(schema)

        workingTable.printTableByAttr(attrList, conditions, joinType)

    def __splitColAndTable(self, conditionVal):
        '''
    	Purpose : Split a condition into a table and a column
    	Parameters :
    		conditionVal: The value to parse
    	Returns: table, column tuple
        '''
        table = None
        column = None

        splitTable = conditionVal.split('.')
        if(len(splitTable) > 1):
            table = splitTable[0].strip()
            column = splitTable[1].strip()
        else:
            column = splitTable[0].strip()
        return table, column

    def __addTableNameToRow(self, tname, row):
        '''
        Purpose : Add a table's name to a row's keys
        Parameters : 
            tname: The name of the table to prepend to the row's keys
            row: The row to correct
        Returns: A new row with the table name prepended to each key
        '''
        newRow = {}
        for k, v in list(row.items()):
            newRow[tname + "." + k] = v 
        return newRow

        

    def __parseTables(self):
        '''
        Purpose:    Helper function to parse table/column pairs.  
        Parameters: None
        Returns:    Dictionary of table/column pairs.
        '''
        splitQuery = re.split("from", self.queryInput, flags=re.IGNORECASE)
        columns = splitQuery[0]
        predicate = re.split("where|on", splitQuery[1], flags=re.IGNORECASE)
        tables = predicate[0]
        conditions = None
        if len(predicate) == 2:
            conditions = predicate[1].strip()
        columns = columns.strip()
        columns = columns.split(",")
        tables = tables.strip()
        tables, joinType = self.__splitOnJoin(tables)
        fields = {}
        aliases = {}
        for table in tables:
            table = table.strip()

            # split on space to check for aliasing 
            table = table.split()
            tableName = table[0]
            if(len(table) > 1):
                aliases[table[1]] = tableName
            
            fields[tableName] = []
            for column in columns:
                column = column.strip()
                column = column.split(".")
                if len(column) != 2:
                    fields[tableName].append(column[0])
                else:
                    if column[0] == table:
                        fields[tableName].append(column[1])


        return fields, aliases, conditions, joinType

    def __splitOnJoin(self,text):

        # Check for an inner join 
        result = re.split(",|inner join", text, flags=re.IGNORECASE)
        if(len(result) > 1):
            return [x.lower() for x in result], Joins.INNER_JOIN

        # Check for a left outer join 
        result = re.split("left outer join", text, flags=re.IGNORECASE)
        if(len(result) > 1):
            return [x.lower() for x in result], Joins.LEFT_OUTER_JOIN

        # Check for a right outer join 
        result = re.split("right outer join", text, flags=re.IGNORECASE)
        if(len(result) > 1):
            return [x.lower() for x in result], Joins.RIGHT_OUTER_JOIN

        return [text.lower()], Joins.NO_JOIN

    def __replaceAliasesInConditional(self, conditional, aliases):
        '''
    	Purpose : Replace alias names in a conditional with table names
    	Parameters :
    		conditional: The condition list to replace,
            aliases: A dictionary mapping aliases to table names
    	Returns: A new list with the aliases replaced with table names
        '''
        if conditional is None: return None 

        conditional = [x.strip() for x in conditional]
        
        # Set all aliases to lowercase in conditional
        for i in range(len(conditional)):
            dotIndex = conditional[i].find('.')
            conditional[i] = conditional[i][0:dotIndex].lower() + conditional[i][dotIndex:]
        #set the provided conditions
        conditions = conditional
        for alias, trueName in list(aliases.items()):
            if conditional[0].startswith(alias + "."):
                conditions[0] = conditional[0].replace(alias, trueName)

            if conditions[2].startswith(alias + "."):
                conditions[2] = conditional[2].replace(alias, trueName)
        return conditions